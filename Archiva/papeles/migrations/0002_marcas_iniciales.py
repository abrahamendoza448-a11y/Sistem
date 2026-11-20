from django.db import migrations

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


def cargar(apps, schema_editor):
    Marca = apps.get_model("papeles", "Marca")
    for s, c, n, sig, uso in MARCAS:
        Marca.objects.get_or_create(codigo=c, defaults={"simbolo": s, "nombre": n, "significado": sig, "uso": uso,
                                                        "aprobacion_texto": "Estándar inicial (propuesta)"})


class Migration(migrations.Migration):
    dependencies = [("papeles", "0001_initial")]
    operations = [migrations.RunPython(cargar, migrations.RunPython.noop)]
