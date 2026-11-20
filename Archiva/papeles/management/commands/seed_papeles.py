"""Datos de demostración del módulo de papeles de trabajo y la tabla inicial de marcas. Es repetible sin duplicar."""
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from core.models import Dependencia, Documento
from core.services import sha256_subido

from papeles.models import AuditoriaInterna, DocumentoLegajo, LineaPapel, Marca, Objetivo, PapelTrabajo
from papeles.services import siguiente_codigo

MARCAS = [
    ("✓", "V", "Verificado", "Dato cotejado con el documento de respaldo", "Cifras, fechas y nombres contrastados con la fuente"),
    ("Σ", "S", "Sumado", "Suma comprobada (casteo)", "Totales de columnas y cuentas"),
    ("↻", "R", "Recalculado", "Cálculo rehecho sin diferencia", "Retenciones, intereses, depreciaciones, saldos"),
    ("Ⓒ", "C", "Confirmado", "Confirmado con un tercero o con otra unidad", "Respuestas a solicitudes de confirmación"),
    ("◉", "I", "Inspeccionado", "Verificado físicamente", "Bienes, obras, existencias"),
    ("Ⓐ", "A", "Autorizado", "Cuenta con firma o aprobación de la autoridad competente", "Resoluciones, órdenes, comprobantes"),
    ("Ⓝ", "N", "Cumple norma", "Cumple la norma o el reglamento aplicable", "Procesos de contratación, pagos"),
    ("≠", "D", "Diferencia", "No coincide; requiere explicación", "Cuando se detecta una discrepancia"),
    ("⊗", "X", "Sin respaldo", "No se encontró el documento de respaldo", "Operación sin soporte en el sistema"),
    ("▲", "H", "Pasa a observación", "Se lleva a una cédula de observación o hallazgo", "Solo por decisión del auditor"),
    ("○", "P", "Pendiente", "Falta información o verificación", "Procedimiento aún no concluido"),
]


def cargar_marcas():
    for s, c, n, sig, uso in MARCAS:
        Marca.objects.get_or_create(codigo=c, defaults={"simbolo": s, "nombre": n, "significado": sig, "uso": uso,
                                                        "aprobacion_texto": "Estándar inicial (propuesta)"})


class Command(BaseCommand):
    help = "Carga la tabla de marcas y una auditoría de ejemplo"

    def add_arguments(self, p):
        p.add_argument("--solo-marcas", action="store_true")

    def handle(self, *a, **o):
        cargar_marcas()
        if o["solo_marcas"] or AuditoriaInterna.objects.exists():
            return
        aud_user = User.objects.filter(username="auditor").first()
        admin = User.objects.filter(username="admin").first()
        dep = Dependencia.objects.filter(sigla="FIN").first() or Dependencia.objects.first()
        if not dep:
            self.stdout.write("Falta ejecutar seed_demo antes (no hay dependencias).")
            return
        a = AuditoriaInterna.objects.create(nombre="Auditoría de ejemplo: gastos de funcionamiento", dependencia_auditada=dep)
        for i, t in enumerate(["Evaluar si los gastos de funcionamiento cuentan con respaldo documental suficiente.",
                               "Verificar que los saldos de las cédulas coincidan con sus detalles."], 1):
            Objetivo.objects.create(auditoria=a, numero=i, texto=t)

        def doc(tipo, area, titulo, texto, aud=None):
            area, n, codigo = siguiente_codigo(tipo, aud, area)
            d = Documento(titulo=f"{codigo} {titulo}", dependencia=dep, nivel_acceso="DEPENDENCIA", texto=texto, creado_por=admin)
            d.archivo.save("ejemplo.txt", ContentFile(texto.encode("utf-8")), save=False)
            d.sha256 = sha256_subido(d.archivo)
            d.save()
            return DocumentoLegajo.objects.create(documento=d, tipo=tipo, auditoria=aud, area=area, correlativo=n, codigo_archivo=codigo).documento

        doc("LP", "A", "Organigrama de la entidad", "Estructura organizacional vigente.")
        doc("LP", "A", "Manual de funciones", "Funciones de cada unidad.")
        d1 = doc("LC", "C", "Comprobante de egreso 0345", "Comprobante de egreso N 0345. Total pagado Bs 1.500,00", a)
        d2 = doc("LC", "C", "Comprobante de egreso 0346", "Comprobante de egreso N 0346. Total pagado Bs 2300.50", a)
        d3 = doc("LC", "C", "Comprobante de egreso 0347", "Sin texto legible.", a)
        p1 = PapelTrabajo.objects.create(auditoria=a, codigo="C-1", titulo="Cédula sumaria de gastos de funcionamiento", elaborado_por=aud_user, supervisado_por=admin)
        p2 = PapelTrabajo.objects.create(auditoria=a, codigo="C-1.1", titulo="Cédula analítica: comprobantes de egreso", elaborado_por=aud_user)
        LineaPapel.objects.create(papel=p1, orden=1, concepto="Gastos de funcionamiento (total)", importe="3800.50", ref_papel="C-1.1")
        LineaPapel.objects.create(papel=p2, orden=1, concepto="Comprobante 0345", importe="1500.00", documento=d1, folio="1", ref_papel="LP-A-001")
        LineaPapel.objects.create(papel=p2, orden=2, concepto="Comprobante 0346", importe="2300.50", documento=d2, folio="1")
        LineaPapel.objects.create(papel=p2, orden=3, concepto="Comprobante 0347", importe="500.00", documento=d3, folio="1")
        LineaPapel.objects.create(papel=p2, orden=4, concepto="Pago sin comprobante", importe="120.00")
        self.stdout.write(self.style.SUCCESS("Módulo de papeles de trabajo: datos de ejemplo cargados."))
