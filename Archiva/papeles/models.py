"""Papeles de trabajo de la UAI: marcas, legajos, referencias, objetivos fijos y adendas."""
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone


class Marca(models.Model):
    """Índice-tabla de marcas estandarizadas. Una marca usada nunca se borra: se retira."""
    ESTADOS = [("vigente", "Vigente"), ("retirada", "Retirada")]
    simbolo = models.CharField("Símbolo", max_length=4)
    codigo = models.CharField("Código único", max_length=6, unique=True)
    nombre = models.CharField(max_length=60)
    significado = models.CharField(max_length=200)
    uso = models.CharField("Cuándo se usa", max_length=200, blank=True)
    estado = models.CharField(max_length=8, choices=ESTADOS, default="vigente")
    version = models.PositiveIntegerField(default=1)
    aprobado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    aprobacion_texto = models.CharField("Aprobación", max_length=120, blank=True)

    class Meta:
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.simbolo} {self.codigo} · {self.nombre}"


class AuditoriaInterna(models.Model):
    """Una auditoría de la UAI. Sus objetivos quedan fijos; solo cambian por adenda."""
    nombre = models.CharField(max_length=200)
    dependencia_auditada = models.ForeignKey("core.Dependencia", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    creada = models.DateTimeField(default=timezone.now)
    creada_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-id"]
        verbose_name = "auditoría interna"
        verbose_name_plural = "auditorías internas"

    def __str__(self):
        return self.nombre

    def get_absolute_url(self):
        return reverse("uai_auditoria", args=[self.pk])


class _Inmutable(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionError("Este registro es fijo; los cambios se hacen mediante adenda.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Este registro no se puede eliminar.")


class Objetivo(_Inmutable):
    auditoria = models.ForeignKey(AuditoriaInterna, on_delete=models.CASCADE, related_name="objetivos")
    numero = models.PositiveSmallIntegerField()
    texto = models.TextField()

    class Meta:
        ordering = ["numero"]
        unique_together = ("auditoria", "numero")

    def vigente(self):
        """Texto vigente: el de la última adenda, o el original."""
        ultima = self.adendas.order_by("-numero").first()
        return ultima.texto_nuevo if ultima else self.texto


class Adenda(_Inmutable):
    auditoria = models.ForeignKey(AuditoriaInterna, on_delete=models.CASCADE, related_name="adendas")
    numero = models.PositiveSmallIntegerField()
    objetivo = models.ForeignKey(Objetivo, on_delete=models.PROTECT, related_name="adendas")
    texto_anterior = models.TextField()
    texto_nuevo = models.TextField()
    justificacion = models.TextField()
    aprobada_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["numero"]
        unique_together = ("auditoria", "numero")


class DocumentoLegajo(models.Model):
    """Ubica un documento de ARCHIVA en el legajo permanente o corriente, con su código de archivo."""
    TIPOS = [("LP", "Legajo permanente"), ("LC", "Legajo corriente")]
    documento = models.OneToOneField("core.Documento", on_delete=models.CASCADE, related_name="legajo")
    tipo = models.CharField("Tipo de legajo", max_length=2, choices=TIPOS)
    auditoria = models.ForeignKey(AuditoriaInterna, null=True, blank=True, on_delete=models.PROTECT, related_name="documentos_legajo")
    area = models.CharField("Área o sección", max_length=8)
    correlativo = models.PositiveIntegerField()
    codigo_archivo = models.CharField(max_length=30)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["auditoria", "codigo_archivo"], condition=Q(auditoria__isnull=False), name="uq_codigo_lc"),
            models.UniqueConstraint(fields=["codigo_archivo"], condition=Q(auditoria__isnull=True), name="uq_codigo_lp"),
            models.CheckConstraint(condition=(Q(tipo="LC", auditoria__isnull=False) | Q(tipo="LP", auditoria__isnull=True)), name="ck_tipo_legajo"),
        ]

    def __str__(self):
        return self.codigo_archivo


class PapelTrabajo(models.Model):
    auditoria = models.ForeignKey(AuditoriaInterna, on_delete=models.CASCADE, related_name="papeles")
    codigo = models.CharField("Código de referencia (ej. C-1, C-1.1)", max_length=30)
    titulo = models.CharField(max_length=200)
    elaborado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    supervisado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        unique_together = ("auditoria", "codigo")
        verbose_name_plural = "papeles de trabajo"

    def __str__(self):
        return f"{self.codigo} · {self.titulo}"

    def get_absolute_url(self):
        return reverse("uai_papel", args=[self.pk])


class LineaPapel(models.Model):
    ESTADOS = [("", "Sin marca"), ("sugerida", "Sugerida"), ("confirmada", "Confirmada")]
    papel = models.ForeignKey(PapelTrabajo, on_delete=models.CASCADE, related_name="lineas")
    orden = models.PositiveIntegerField()
    concepto = models.CharField(max_length=255)
    importe = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    documento = models.ForeignKey("core.Documento", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    folio = models.CharField(max_length=20, blank=True)
    ref_papel = models.CharField("Referencia (papel o documento del legajo permanente)", max_length=30, blank=True)
    marca = models.ForeignKey(Marca, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    marca_estado = models.CharField(max_length=10, choices=ESTADOS, blank=True, default="")
    confianza = models.CharField(max_length=8, blank=True)
    nota = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["orden"]
