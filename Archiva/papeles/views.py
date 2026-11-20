from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import Auditoria, Documento, Rol
from core.services import analizar_documento, extraer_texto, rol_de, rol_requerido, sha256_subido

from . import forms as F
from . import services as S
from .models import Adenda, AuditoriaInterna, DocumentoLegajo, LineaPapel, Marca, Objetivo, PapelTrabajo

VER = (Rol.ADMIN, Rol.AUDITOR, Rol.ARCHIVISTA)
EDITAR = (Rol.ADMIN, Rol.AUDITOR)
CARGAR = (Rol.ADMIN, Rol.AUDITOR, Rol.ARCHIVISTA)
APROBAR = (Rol.ADMIN,)


def _form_page(request, form, titulo, volver, multipart=False):
    return render(request, "papeles/form.html", {"form": form, "titulo": titulo, "volver": volver, "multipart": multipart})


@login_required
@rol_requerido(*VER)
def inicio(request):
    auds = AuditoriaInterna.objects.annotate(n_papeles=Count("papeles", distinct=True), n_docs=Count("documentos_legajo", distinct=True))
    return render(request, "papeles/inicio.html", {"auditorias": auds, "n_lp": DocumentoLegajo.objects.filter(tipo="LP").count()})


# --- Marcas ---------------------------------------------------------------------------------
@login_required
@rol_requerido(*VER)
def marcas(request):
    return render(request, "papeles/marcas.html", {"marcas": Marca.objects.all(), "puede_aprobar": rol_de(request.user) in APROBAR})


@login_required
@rol_requerido(*APROBAR)
def marca_nueva(request):
    form = F.MarcaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        m = form.save(commit=False)
        m.aprobado_por = request.user
        m.save()
        Auditoria.registrar(request, "MARCA_ALTA", m.codigo, f"{m.simbolo} {m.nombre}")
        messages.success(request, f"Marca {m.codigo} agregada.")
        return redirect("uai_marcas")
    return _form_page(request, form, "Agregar marca nueva", "uai_marcas")


@require_POST
@login_required
@rol_requerido(*APROBAR)
def marca_retirar(request, pk):
    m = get_object_or_404(Marca, pk=pk)
    m.estado, m.version = "retirada", m.version + 1
    m.save()
    Auditoria.registrar(request, "MARCA_RETIRO", m.codigo)
    messages.success(request, f"Marca {m.codigo} retirada. Se conserva su significado histórico.")
    return redirect("uai_marcas")


# --- Legajos -------------------------------------------------------------------------------------
@login_required
@rol_requerido(*VER)
def legajo_permanente(request):
    docs = S.legajos_ordenados(DocumentoLegajo.objects.filter(tipo="LP").select_related("documento"))
    return render(request, "papeles/legajo_permanente.html", {"docs": docs})


@login_required
@rol_requerido(*CARGAR)
def documento_cargar(request):
    form = F.CargaLegajoForm(request.POST or None, request.FILES or None)
    if request.method == "GET":
        from core.services import dependencia_de
        if dependencia_de(request.user):
            form.fields["dependencia"].initial = dependencia_de(request.user)
        if a := request.GET.get("auditoria"):
            form.fields["auditoria"].initial = a
            form.fields["tipo"].initial = "LC"
    if request.method == "POST" and form.is_valid():
        c = form.cleaned_data
        with transaction.atomic():
            area, n, codigo = S.siguiente_codigo(c["tipo"], c["auditoria"], c["area"])
            doc = Documento(titulo=f"{codigo} {c['titulo']}", dependencia=c["dependencia"], nivel_acceso=c["nivel_acceso"],
                            archivo=c["archivo"], creado_por=request.user)
            doc.sha256 = sha256_subido(doc.archivo)
            doc.save()
            doc.texto = extraer_texto(doc.archivo.path)
            analizar_documento(doc)
            doc.save()
            DocumentoLegajo.objects.create(documento=doc, tipo=c["tipo"], auditoria=c["auditoria"], area=area,
                                           correlativo=n, codigo_archivo=codigo)
        Auditoria.registrar(request, "LEGAJO_CARGA", doc.codigo, f"{codigo} · {dict(DocumentoLegajo.TIPOS)[c['tipo']]}")
        messages.success(request, f"Documento cargado como {codigo} en el {dict(DocumentoLegajo.TIPOS)[c['tipo']].lower()}.")
        return redirect("uai_legajo_permanente" if c["tipo"] == "LP" else "uai_auditoria", *([] if c["tipo"] == "LP" else [c["auditoria"].pk]))
    return _form_page(request, form, "Cargar documento al legajo", "uai_inicio", multipart=True)


# --- Auditorías, objetivos fijos y adendas ------------------------------------------------------------
@login_required
@rol_requerido(*EDITAR)
def auditoria_nueva(request):
    form = F.AuditoriaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            a = form.save(commit=False)
            a.creada_por = request.user
            a.save()
            for i, t in enumerate(form.cleaned_data["objetivos"], 1):
                Objetivo.objects.create(auditoria=a, numero=i, texto=t)
        Auditoria.registrar(request, "UAI_AUDITORIA_ALTA", a.nombre, f"{len(form.cleaned_data['objetivos'])} objetivos fijos")
        messages.success(request, "Auditoría creada. Los objetivos quedaron fijos.")
        return redirect(a)
    return _form_page(request, form, "Nueva auditoría", "uai_inicio")


@login_required
@rol_requerido(*VER)
def auditoria(request, pk):
    a = get_object_or_404(AuditoriaInterna, pk=pk)
    objetivos = [(o, o.vigente(), o.vigente() != o.texto) for o in a.objetivos.all()]
    return render(request, "papeles/auditoria.html", {
        "a": a, "objetivos": objetivos, "adendas": a.adendas.select_related("objetivo", "aprobada_por"),
        "docs": S.legajos_ordenados(a.documentos_legajo.select_related("documento")), "papeles": S.papeles_ordenados(a),
        "puede_editar": rol_de(request.user) in EDITAR, "puede_aprobar": rol_de(request.user) in APROBAR})


@login_required
@rol_requerido(*APROBAR)
def adenda_nueva(request, pk):
    a = get_object_or_404(AuditoriaInterna, pk=pk)
    form = F.AdendaForm(a, request.POST or None)
    if request.method == "POST" and form.is_valid():
        o = form.cleaned_data["objetivo"]
        with transaction.atomic():
            n = (a.adendas.order_by("-numero").values_list("numero", flat=True).first() or 0) + 1
            Adenda.objects.create(auditoria=a, numero=n, objetivo=o, texto_anterior=o.vigente(), texto_nuevo=form.cleaned_data["texto_nuevo"],
                                  justificacion=form.cleaned_data["justificacion"], aprobada_por=request.user)
        Auditoria.registrar(request, "UAI_ADENDA", a.nombre, f"Adenda {n} al objetivo {o.numero}")
        messages.success(request, f"Adenda {n} registrada. El objetivo original se conserva.")
        return redirect(a)
    return _form_page(request, form, f"Nueva adenda · {a.nombre}", "uai_auditoria")


# --- Papeles de trabajo --------------------------------------------------------------------------------------
@login_required
@rol_requerido(*EDITAR)
def papel_nuevo(request, pk):
    a = get_object_or_404(AuditoriaInterna, pk=pk)
    form = F.PapelForm(request.POST or None)
    if request.method == "GET":
        form.fields["elaborado_por"].initial = request.user
    if request.method == "POST" and form.is_valid():
        p = form.save(commit=False)
        p.auditoria = a
        try:
            p.save()
        except Exception:
            form.add_error("codigo", "Ya existe un papel con ese código en esta auditoría.")
        else:
            Auditoria.registrar(request, "UAI_PAPEL_ALTA", p.codigo, p.titulo)
            return redirect(p)
    return _form_page(request, form, f"Nuevo papel de trabajo · {a.nombre}", "uai_auditoria")


def _docs_para(a):
    ids = DocumentoLegajo.objects.filter(auditoria=a).values_list("documento_id", flat=True)
    lp = DocumentoLegajo.objects.filter(tipo="LP").values_list("documento_id", flat=True)
    return Documento.objects.filter(pk__in=list(ids) + list(lp)).order_by("titulo")


@login_required
@rol_requerido(*VER)
def papel(request, pk):
    p = get_object_or_404(PapelTrabajo.objects.select_related("auditoria"), pk=pk)
    filas = []
    for ln in p.lineas.select_related("marca", "documento"):
        res = S.resolver_ref(p.auditoria, ln.ref_papel) if ln.ref_papel else None
        filas.append({"l": ln, "ref": res, "rota": bool(ln.ref_papel) and res is None})
    editar = rol_de(request.user) in EDITAR
    form = F.LineaForm(docs=_docs_para(p.auditoria)) if editar else None
    return render(request, "papeles/papel.html", {
        "p": p, "filas": filas, "total": S.total_papel(p), "coref": S.coreferencias(p), "form": form, "editar": editar,
        "marcas": Marca.objects.filter(estado="vigente"),
        "leyenda": {f["l"].marca for f in filas if f["l"].marca and f["l"].marca_estado == "confirmada"}})


@require_POST
@login_required
@rol_requerido(*EDITAR)
def linea_nueva(request, pk):
    p = get_object_or_404(PapelTrabajo, pk=pk)
    form = F.LineaForm(request.POST, docs=_docs_para(p.auditoria))
    if form.is_valid():
        ln = form.save(commit=False)
        ln.papel = p
        ln.orden = (p.lineas.order_by("-orden").values_list("orden", flat=True).first() or 0) + 1
        ln.save()
    else:
        messages.error(request, "Revise la línea: " + "; ".join(f"{k}: {', '.join(v)}" for k, v in form.errors.items()))
    return redirect(p)


@require_POST
@login_required
@rol_requerido(*EDITAR)
def papel_sugerir(request, pk):
    p = get_object_or_404(PapelTrabajo, pk=pk)
    n = S.sugerir_marcas(p)
    Auditoria.registrar(request, "UAI_MARCAS_SUGERIDAS", p.codigo, f"{n} sugerencias (reglas locales)")
    messages.success(request, f"{n} marcas sugeridas. Revíselas y confirme o rechace cada una.")
    return redirect(p)


@require_POST
@login_required
@rol_requerido(*EDITAR)
def linea_confirmar(request, pk):
    ln = get_object_or_404(LineaPapel.objects.select_related("papel"), pk=pk)
    m = Marca.objects.filter(pk=request.POST.get("marca") or 0, estado="vigente").first()
    if not m:
        messages.error(request, "Elija una marca vigente.")
        return redirect(ln.papel)
    ln.marca, ln.marca_estado = m, "confirmada"
    ln.save(update_fields=["marca", "marca_estado"])
    Auditoria.registrar(request, "UAI_MARCA_CONFIRMADA", ln.papel.codigo, f"línea {ln.orden}: {m.codigo}")
    return redirect(f"{ln.papel.get_absolute_url()}#l{ln.pk}")


@require_POST
@login_required
@rol_requerido(*EDITAR)
def linea_rechazar(request, pk):
    ln = get_object_or_404(LineaPapel.objects.select_related("papel"), pk=pk)
    ln.marca, ln.marca_estado, ln.confianza, ln.nota = None, "", "", ""
    ln.save(update_fields=["marca", "marca_estado", "confianza", "nota"])
    Auditoria.registrar(request, "UAI_MARCA_RECHAZADA", ln.papel.codigo, f"línea {ln.orden}")
    return redirect(f"{ln.papel.get_absolute_url()}#l{ln.pk}")


@login_required
@rol_requerido(*VER)
def papel_descargar(request, pk, formato):
    p = get_object_or_404(PapelTrabajo.objects.select_related("auditoria"), pk=pk)
    if formato == "xlsx":
        data, tipo = S.libro_excel(p.auditoria, activo=p), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        nombre = f"papeles_{p.auditoria_id}.xlsx"
    elif formato == "docx":
        data, tipo = S.papel_word(p), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        nombre = f"papel_{p.codigo}.docx"
    else:
        raise Http404
    Auditoria.registrar(request, "UAI_DESCARGA", p.codigo, formato)
    r = HttpResponse(data, content_type=tipo)
    r["Content-Disposition"] = f'attachment; filename="{nombre}"'
    return r


@login_required
@rol_requerido(*VER)
def libro(request, pk):
    a = get_object_or_404(AuditoriaInterna, pk=pk)
    Auditoria.registrar(request, "UAI_DESCARGA", a.nombre, "libro xlsx")
    r = HttpResponse(S.libro_excel(a), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    r["Content-Disposition"] = f'attachment; filename="papeles_auditoria_{a.pk}.xlsx"'
    return r


@login_required
@rol_requerido(*VER)
def verificador(request, pk):
    a = get_object_or_404(AuditoriaInterna, pk=pk)
    return render(request, "papeles/verificador.html", {"a": a, "hallazgos": S.verificador(a)})


@login_required
@rol_requerido(*VER)
def informe(request, pk):
    a = get_object_or_404(AuditoriaInterna, pk=pk)
    resumen, dif, total_l, conf = [], [], 0, 0
    for p in S.papeles_ordenados(a):
        lns = list(p.lineas.select_related("marca"))
        resumen.append((p, S.total_papel(p), len(lns)))
        for ln in lns:
            total_l += 1
            conf += ln.marca_estado == "confirmada"
            if ln.marca and ln.marca.codigo in ("D", "X", "H", "P"):
                dif.append((p, ln))
    pct = round(conf * 100 / total_l) if total_l else None
    return render(request, "papeles/informe.html", {"a": a, "objetivos": a.objetivos.all(), "adendas": a.adendas.all(), "resumen": resumen,
                                                     "dif": dif, "total_l": total_l, "conf": conf, "pct": pct})
