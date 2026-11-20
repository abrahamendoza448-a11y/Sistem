import io
import tempfile
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from openpyxl import load_workbook

from core.models import Auditoria, Dependencia, Documento, Perfil, Rol

from . import services as S
from .models import Adenda, AuditoriaInterna, DocumentoLegajo, LineaPapel, Marca, Objetivo, PapelTrabajo

TMP = tempfile.mkdtemp()
CLAVE = "x-Clave-segura-1"


@override_settings(MEDIA_ROOT=TMP, DOCUMENTOS_ROOT=TMP)
class PapelesTests(TestCase):
    def setUp(self):
        self.dep = Dependencia.objects.create(nombre="UAI", sigla="UAI")
        self.admin = self._u("jefe", Rol.ADMIN)
        self.aud = self._u("audi", Rol.AUDITOR)
        self.func = self._u("func", Rol.FUNCIONARIO)
        self.a = AuditoriaInterna.objects.create(nombre="Auditoría X", dependencia_auditada=self.dep)
        self.o1 = Objetivo.objects.create(auditoria=self.a, numero=1, texto="Objetivo original")

    def _u(self, n, rol):
        u = User.objects.create_user(n, password=CLAVE)
        Perfil.objects.create(user=u, rol=rol, dependencia=self.dep)
        return u

    def _doc(self, tipo, area, titulo, texto="x"):
        self.client.login(username="audi", password=CLAVE)
        return self.client.post(reverse("uai_cargar"), {
            "tipo": tipo, "auditoria": self.a.pk if tipo == "LC" else "", "area": area, "titulo": titulo, "dependencia": self.dep.pk,
            "nivel_acceso": "DEPENDENCIA", "archivo": SimpleUploadedFile("a.txt", texto.encode())})

    def test_marcas_iniciales_por_migracion(self):
        self.assertTrue(Marca.objects.filter(codigo__in=["V", "S", "D", "X", "P"]).count() == 5)

    def test_tipo_de_legajo_es_obligatorio(self):
        r = self._doc("", "C", "Sin tipo")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(DocumentoLegajo.objects.count(), 0)
        r = self.client.post(reverse("uai_cargar"), {"tipo": "LC", "auditoria": "", "area": "C", "titulo": "t", "dependencia": self.dep.pk,
                                                    "nivel_acceso": "DEPENDENCIA", "archivo": SimpleUploadedFile("a.txt", b"x")})
        self.assertEqual(DocumentoLegajo.objects.count(), 0)  # corriente sin auditoría

    def test_numeracion_en_el_titulo_y_orden_natural(self):
        for i in range(3):
            self._doc("LC", "C", f"Doc {i}")
        self._doc("LP", "A", "Organigrama")
        codigos = [d.codigo_archivo for d in S.legajos_ordenados(DocumentoLegajo.objects.filter(tipo="LC"))]
        self.assertEqual(codigos, [f"LC{self.a.pk}-C-00{i}" for i in (1, 2, 3)])
        lp = DocumentoLegajo.objects.get(tipo="LP")
        self.assertEqual(lp.codigo_archivo, "LP-A-001")
        self.assertTrue(lp.documento.titulo.startswith("LP-A-001 "))
        self.assertIsNone(lp.auditoria)
        self.assertEqual(S.clave_natural("C-1.2") < S.clave_natural("C-1.10"), True)

    def test_legajo_permanente_es_una_seccion(self):
        self._doc("LP", "A", "Manual")
        r = self.client.get(reverse("uai_legajo_permanente"))
        self.assertContains(r, "LP-A-001")
        self.assertContains(r, "Legajo permanente")

    def test_objetivos_fijos_y_adenda(self):
        with self.assertRaises(PermissionError):
            self.o1.texto = "cambiado"
            self.o1.save()
        self.client.login(username="audi", password=CLAVE)  # el auditor no aprueba adendas
        self.assertEqual(self.client.get(reverse("uai_adenda_nueva", args=[self.a.pk])).status_code, 403)
        self.client.login(username="jefe", password=CLAVE)
        r = self.client.post(reverse("uai_adenda_nueva", args=[self.a.pk]), {"objetivo": self.o1.pk, "texto_nuevo": "Objetivo ajustado", "justificacion": "Cambió el alcance"})
        self.assertEqual(r.status_code, 302)
        ad = Adenda.objects.get()
        self.assertEqual((ad.numero, ad.texto_anterior), (1, "Objetivo original"))
        self.o1.refresh_from_db()
        self.assertEqual(self.o1.texto, "Objetivo original")
        self.assertEqual(self.o1.vigente(), "Objetivo ajustado")
        with self.assertRaises(PermissionError):
            ad.delete()
        self.assertTrue(Auditoria.objects.filter(accion="UAI_ADENDA").exists())

    def _papeles(self):
        p1 = PapelTrabajo.objects.create(auditoria=self.a, codigo="C-1", titulo="Sumaria", elaborado_por=self.aud, supervisado_por=self.admin)
        p2 = PapelTrabajo.objects.create(auditoria=self.a, codigo="C-1.1", titulo="Analítica", elaborado_por=self.aud)
        self._doc("LC", "C", "Comprobante 1", "Total Bs 1.500,00")
        d = Documento.objects.get(titulo__contains="Comprobante 1")
        l1 = LineaPapel.objects.create(papel=p1, orden=1, concepto="Total", importe=Decimal("2000.00"), ref_papel="C-1.1")
        l2 = LineaPapel.objects.create(papel=p2, orden=1, concepto="Comp 1", importe=Decimal("1500.00"), documento=d)
        l3 = LineaPapel.objects.create(papel=p2, orden=2, concepto="Sin respaldo", importe=Decimal("500.00"))
        return p1, p2, l1, l2, l3

    def test_sugerencias_y_confirmacion(self):
        p1, p2, l1, l2, l3 = self._papeles()
        self.assertEqual(S.sugerir_marcas(p2), 2)
        self.assertEqual(S.sugerir_marcas(p1), 1)
        for ln in (l1, l2, l3):
            ln.refresh_from_db()
        self.assertEqual(l2.marca.codigo, "V")
        self.assertEqual(l3.marca.codigo, "X")
        self.assertEqual(l1.marca.codigo, "S")  # 1500 + 500 = 2000
        self.assertEqual(l1.marca_estado, "sugerida")
        self.client.login(username="audi", password=CLAVE)
        r = self.client.post(reverse("uai_linea_confirmar", args=[l2.pk]), {"marca": l2.marca_id})
        self.assertEqual(r.status_code, 302)
        l2.refresh_from_db()
        self.assertEqual(l2.marca_estado, "confirmada")
        self.assertEqual(S.sugerir_marcas(p2), 1)  # no vuelve a sugerir lo confirmado
        self.assertTrue(Auditoria.objects.filter(accion="UAI_MARCA_CONFIRMADA").exists())

    def test_diferencia_de_suma(self):
        p1, p2, l1, l2, l3 = self._papeles()
        l1.importe = Decimal("3800.50")
        l1.save()
        S.sugerir_marcas(p1)
        l1.refresh_from_db()
        self.assertEqual(l1.marca.codigo, "D")

    def test_coreferencia_es_un_enlace_a_la_referencia(self):
        p1, p2, l1, *_ = self._papeles()
        self.client.login(username="audi", password=CLAVE)
        r = self.client.get(reverse("uai_papel", args=[p2.pk]))
        self.assertContains(r, f'href="{reverse("uai_papel", args=[p1.pk])}#l{l1.pk}"')
        r = self.client.get(reverse("uai_papel", args=[p1.pk]))
        self.assertContains(r, f'id="l{l1.pk}"')

    def test_referencia_al_legajo_permanente(self):
        p1, p2, l1, l2, l3 = self._papeles()
        self._doc("LP", "A", "Organigrama")
        l3.ref_papel = "LP-A-001"
        l3.save()
        self.assertEqual(S.resolver_ref(self.a, "LP-A-001")[0], "legajo")
        S.sugerir_marcas(p2)
        l3.refresh_from_db()
        self.assertNotEqual(getattr(l3.marca, "codigo", None), "X")

    def test_verificador(self):
        p1, p2, l1, l2, l3 = self._papeles()
        l3.ref_papel = "Z-9"
        l3.save()
        tipos = {t for _, t, _ in S.verificador(self.a)}
        self.assertTrue({"Referencia rota", "Papel sin firma", "Marca sin confirmar", "Saldo que no cuadra"} <= tipos or {"Referencia rota", "Papel sin firma", "Marca sin confirmar"} <= tipos)

    def test_nueva_marca_y_retiro(self):
        self.client.login(username="jefe", password=CLAVE)
        self.client.post(reverse("uai_marca_nueva"), {"simbolo": "Q", "codigo": "q", "nombre": "Nueva", "significado": "Prueba", "uso": ""})
        m = Marca.objects.get(codigo="Q")
        self.assertEqual(m.aprobado_por, self.admin)
        self.client.post(reverse("uai_marca_retirar", args=[m.pk]))
        m.refresh_from_db()
        self.assertEqual((m.estado, m.version), ("retirada", 2))
        self.client.login(username="audi", password=CLAVE)
        self.assertEqual(self.client.post(reverse("uai_marca_nueva"), {}).status_code, 403)

    def test_descargas_con_marcas_y_enlaces(self):
        p1, p2, l1, l2, l3 = self._papeles()
        S.sugerir_marcas(p2)
        S.sugerir_marcas(p1)
        LineaPapel.objects.filter(pk__in=[l1.pk, l2.pk, l3.pk]).update(marca_estado="confirmada")
        self.client.login(username="audi", password=CLAVE)
        r = self.client.get(reverse("uai_papel_descargar", args=[p2.pk, "xlsx"]))
        wb = load_workbook(io.BytesIO(r.content))
        self.assertEqual(wb.sheetnames, ["Índice", "C-1", "C-1.1"])
        ws = wb["C-1"]
        self.assertEqual(ws["D5"].hyperlink.location, "'C-1.1'!A1")
        self.assertIn("Σ S", ws["F5"].value)
        ws2 = wb["C-1.1"]
        textos = [c.value for row in ws2.iter_rows() for c in row if c.value]
        self.assertTrue(any(str(t).startswith("← C-1") for t in textos))
        self.assertTrue(any(c.hyperlink and c.hyperlink.location == "'C-1'!A5" for row in ws2.iter_rows() for c in row))
        r = self.client.get(reverse("uai_papel_descargar", args=[p2.pk, "docx"]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get(reverse("uai_papel_descargar", args=[p2.pk, "pdf"])).status_code, 404)

    def test_permisos_y_pantallas(self):
        self.client.login(username="func", password=CLAVE)
        self.assertEqual(self.client.get(reverse("uai_inicio")).status_code, 403)
        for u in ("jefe", "audi"):
            self.client.login(username=u, password=CLAVE)
            for n, args in (("uai_inicio", []), ("uai_marcas", []), ("uai_legajo_permanente", []), ("uai_cargar", []),
                            ("uai_auditoria", [self.a.pk]), ("uai_verificador", [self.a.pk]), ("uai_informe", [self.a.pk])):
                self.assertEqual(self.client.get(reverse(n, args=args)).status_code, 200, n)

    def test_cadena_de_auditoria_sigue_integra(self):
        self._papeles()
        self.assertTrue(Auditoria.verificar_cadena()[0])
