"""Reglas del módulo: orden natural, referencias, sugerencia de marcas, verificador y exportaciones."""
import io
import re
from decimal import Decimal

from django.db import transaction
from django.db.models import Max, Sum
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.hyperlink import Hyperlink

from .models import DocumentoLegajo, LineaPapel, Marca, PapelTrabajo


def clave_natural(codigo):
    """Orden natural: C-1.2 antes que C-1.10."""
    return [(0, int(p), "") if p.isdigit() else (1, 0, p) for p in re.split(r"(\d+)", codigo or "") if p != ""]


def fmt(n):
    if n is None:
        return ""
    return f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def papeles_ordenados(auditoria):
    return sorted(auditoria.papeles.all(), key=lambda p: clave_natural(p.codigo))


def legajos_ordenados(qs):
    return sorted(qs, key=lambda d: clave_natural(d.codigo_archivo))


@transaction.atomic
def siguiente_codigo(tipo, auditoria, area):
    """Correlativo y código de archivo: LP-A-003 o LC1-C-001. El código encabeza el título del documento."""
    area = re.sub(r"[^A-Za-z0-9]", "", area).upper()
    base = DocumentoLegajo.objects.filter(tipo=tipo, auditoria=auditoria, area=area)
    n = (base.aggregate(m=Max("correlativo"))["m"] or 0) + 1
    prefijo = f"LC{auditoria.pk}" if tipo == "LC" else "LP"
    return area, n, f"{prefijo}-{area}-{n:03d}"


# --- Referencias ---------------------------------------------------------------------------
def resolver_ref(auditoria, ref):
    """Devuelve ('papel', PapelTrabajo) | ('legajo', DocumentoLegajo) | None."""
    ref = (ref or "").strip().upper()
    if not ref:
        return None
    p = auditoria.papeles.filter(codigo__iexact=ref).first()
    if p:
        return ("papel", p)
    d = DocumentoLegajo.objects.filter(codigo_archivo__iexact=ref).filter(
        tipo="LP").first() or DocumentoLegajo.objects.filter(codigo_archivo__iexact=ref, auditoria=auditoria).first()
    return ("legajo", d) if d else None


def coreferencias(papel):
    """Líneas de otros papeles de la auditoría que referencian a este papel."""
    return (LineaPapel.objects.filter(papel__auditoria=papel.auditoria, ref_papel__iexact=papel.codigo)
            .select_related("papel").order_by("papel__codigo", "orden"))


def total_papel(papel):
    return papel.lineas.aggregate(t=Sum("importe"))["t"] or Decimal("0")


# --- Sugerencia de marcas (punto de enchufe para OCR/IA local) --------------------------------
def _variantes(x):
    base = f"{x:.2f}"
    ent = f"{x:,.2f}"
    es = ent.replace(",", "X").replace(".", ",").replace("X", ".")
    return {base, ent, es, base.replace(".", ","), f"{x:.0f}" if x == x.to_integral_value() else base}


def _marca(codigo):
    return Marca.objects.filter(codigo=codigo, estado="vigente").first()


def sugerir_marcas(papel):
    """Propone marcas por reglas deterministas. Todo queda 'sugerida' hasta que el auditor confirme.
    Para usar OCR/IA, reemplazar o ampliar esta función: debe devolver (codigo_marca, confianza, nota)."""
    n = 0
    for ln in papel.lineas.exclude(marca_estado="confirmada"):
        codigo = conf = nota = None
        res = resolver_ref(papel.auditoria, ln.ref_papel) if ln.ref_papel else None
        if ln.ref_papel and res is None:
            codigo, conf, nota = "P", "alta", f"La referencia {ln.ref_papel} no existe todavía."
        elif res and res[0] == "papel" and ln.importe is not None:
            total = total_papel(res[1])
            if total == ln.importe:
                codigo, conf, nota = "S", "alta", f"La suma de {res[1].codigo} ({fmt(total)}) coincide."
            else:
                codigo, conf, nota = "D", "alta", f"{res[1].codigo} suma {fmt(total)} y la cédula dice {fmt(ln.importe)}."
        elif ln.documento_id:
            texto = (ln.documento.texto or "").strip()
            if not texto:
                codigo, conf, nota = "P", "baja", "El documento no tiene texto leído (falta OCR o transcripción)."
            elif ln.importe is not None:
                if any(v in texto for v in _variantes(ln.importe)):
                    codigo, conf, nota = "V", "media", "El importe aparece en el texto del documento."
                else:
                    codigo, conf, nota = "D", "media", "El importe no aparece en el texto del documento."
        elif ln.importe is not None and not res:
            codigo, conf, nota = "X", "alta", "Línea con importe y sin documento de respaldo."
        if codigo:
            m = _marca(codigo)
            if m:
                ln.marca, ln.marca_estado, ln.confianza, ln.nota = m, "sugerida", conf, nota
                ln.save(update_fields=["marca", "marca_estado", "confianza", "nota"])
                n += 1
    return n


# --- Verificador (completitud y consistencia de forma) -----------------------------------------
def verificador(auditoria):
    hall = []
    for p in papeles_ordenados(auditoria):
        if not p.elaborado_por or not p.supervisado_por:
            hall.append((p, "Papel sin firma", "Falta elaborador o supervisor"))
        for ln in p.lineas.select_related("marca"):
            res = resolver_ref(auditoria, ln.ref_papel) if ln.ref_papel else None
            if ln.ref_papel and res is None:
                hall.append((p, "Referencia rota", f"«{ln.concepto}» apunta a {ln.ref_papel}, que no existe"))
            if ln.importe is not None and not ln.documento_id and not ln.ref_papel:
                hall.append((p, "Cifra sin referencia", f"«{ln.concepto}» no tiene documento ni referencia"))
            if ln.marca_estado != "confirmada":
                hall.append((p, "Marca sin confirmar", f"«{ln.concepto}»"))
            elif ln.marca and ln.marca.estado != "vigente":
                hall.append((p, "Marca sin leyenda vigente", f"«{ln.concepto}» usa una marca retirada"))
            if res and res[0] == "papel" and ln.importe is not None and total_papel(res[1]) != ln.importe:
                hall.append((p, "Saldo que no cuadra", f"{p.codigo} dice {fmt(ln.importe)}; {res[1].codigo} suma {fmt(total_papel(res[1]))}"))
    return hall


# --- Exportaciones --------------------------------------------------------------------------------
def _nombre_hoja(codigo):
    return re.sub(r"[\[\]:*?/\\]", "-", codigo)[:31]


def libro_excel(auditoria, activo=None):
    """Libro de Excel con una hoja por papel. Referencias y co-referencias son hipervínculos internos."""
    wb = Workbook()
    ind = wb.active
    ind.title = "Índice"
    ind["A1"] = f"Papeles de trabajo · {auditoria.nombre}"
    ind["A1"].font = Font(bold=True, size=13)
    papeles = papeles_ordenados(auditoria)
    for i, p in enumerate(papeles, start=3):
        c = ind.cell(row=i, column=1, value=p.codigo)
        c.hyperlink = Hyperlink(ref=c.coordinate, location=f"'{_nombre_hoja(p.codigo)}'!A1")
        c.font = Font(color="0563C1", underline="single")
        ind.cell(row=i, column=2, value=p.titulo)
    ind.column_dimensions["A"].width = 14
    ind.column_dimensions["B"].width = 60
    cab = PatternFill("solid", fgColor="E6E2D3")
    for p in papeles:
        ws = wb.create_sheet(_nombre_hoja(p.codigo))
        ws["A1"] = f"{p.codigo} · {p.titulo}"
        ws["A1"].font = Font(bold=True, size=13)
        ws["A2"] = f"Elaboró: {p.elaborado_por or '—'} · Supervisó: {p.supervisado_por or '—'}"
        for j, t in enumerate(["#", "Concepto", "Importe (Bs)", "Referencia", "Respaldo", "Marca"], start=1):
            c = ws.cell(row=4, column=j, value=t)
            c.font, c.fill = Font(bold=True), cab
        usadas = {}
        fila = 5
        for ln in p.lineas.select_related("marca", "documento"):
            ws.cell(row=fila, column=1, value=ln.orden)
            ws.cell(row=fila, column=2, value=ln.concepto)
            ci = ws.cell(row=fila, column=3, value=float(ln.importe) if ln.importe is not None else None)
            ci.number_format = "#,##0.00"
            if ln.ref_papel:
                c = ws.cell(row=fila, column=4, value=f"→ {ln.ref_papel}")
                res = resolver_ref(auditoria, ln.ref_papel)
                if res and res[0] == "papel":
                    c.hyperlink = Hyperlink(ref=c.coordinate, location=f"'{_nombre_hoja(res[1].codigo)}'!A1")
                    c.font = Font(color="0563C1", underline="single")
            if ln.documento:
                ws.cell(row=fila, column=5, value=f"{ln.documento.titulo}" + (f" f.{ln.folio}" if ln.folio else ""))
            if ln.marca:
                ok = ln.marca_estado == "confirmada"
                ws.cell(row=fila, column=6, value=f"{ln.marca.simbolo} {ln.marca.codigo}" + ("" if ok else " ? (sin confirmar)"))
                if ok:
                    usadas[ln.marca.codigo] = ln.marca
            fila += 1
        ws.cell(row=fila, column=2, value="Total").font = Font(bold=True)
        ws.cell(row=fila, column=3, value=float(total_papel(p))).number_format = "#,##0.00"
        fila += 2
        ws.cell(row=fila, column=1, value="Co-referencias (clic para ir al papel de origen)").font = Font(bold=True)
        for co in coreferencias(p):
            fila += 1
            c = ws.cell(row=fila, column=1, value=f"← {co.papel.codigo} · {co.concepto}")
            c.hyperlink = Hyperlink(ref=c.coordinate, location=f"'{_nombre_hoja(co.papel.codigo)}'!A{4 + co.orden}")
            c.font = Font(color="0563C1", underline="single")
        fila += 2
        ws.cell(row=fila, column=1, value="Leyenda de marcas").font = Font(bold=True)
        for m in usadas.values():
            fila += 1
            ws.cell(row=fila, column=1, value=f"{m.simbolo} {m.codigo} — {m.significado}")
        for col, w in zip("ABCDEF", (6, 46, 16, 16, 34, 22)):
            ws.column_dimensions[col].width = w
    if activo and _nombre_hoja(activo.codigo) in wb.sheetnames:
        wb.active = wb.sheetnames.index(_nombre_hoja(activo.codigo))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def papel_word(papel):
    from docx import Document
    d = Document()
    d.add_heading(f"{papel.codigo} · {papel.titulo}", level=1)
    d.add_paragraph(f"Elaboró: {papel.elaborado_por or '—'} · Supervisó: {papel.supervisado_por or '—'}")
    t = d.add_table(rows=1, cols=6)
    t.style = "Table Grid"
    for i, h in enumerate(["#", "Concepto", "Importe (Bs)", "Referencia", "Respaldo", "Marca"]):
        t.rows[0].cells[i].text = h
        t.rows[0].cells[i].paragraphs[0].runs[0].bold = True
    usadas = {}
    for ln in papel.lineas.select_related("marca", "documento"):
        r = t.add_row().cells
        r[0].text, r[1].text, r[2].text = str(ln.orden), ln.concepto, fmt(ln.importe)
        r[3].text = f"→ {ln.ref_papel}" if ln.ref_papel else ""
        r[4].text = (ln.documento.titulo + (f" f.{ln.folio}" if ln.folio else "")) if ln.documento else ""
        if ln.marca:
            ok = ln.marca_estado == "confirmada"
            r[5].text = f"{ln.marca.simbolo} {ln.marca.codigo}" + ("" if ok else " ? (sin confirmar)")
            if ok:
                usadas[ln.marca.codigo] = ln.marca
    r = t.add_row().cells
    r[1].text, r[2].text = "Total", fmt(total_papel(papel))
    d.add_heading("Co-referencias", level=2)
    cos = list(coreferencias(papel))
    for co in cos:
        d.add_paragraph(f"← {co.papel.codigo} · {co.concepto}", style="List Bullet")
    if not cos:
        d.add_paragraph("Ningún papel lo referencia.")
    d.add_heading("Leyenda de marcas", level=2)
    for m in usadas.values():
        d.add_paragraph(f"{m.simbolo} {m.codigo} — {m.significado}", style="List Bullet")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()
