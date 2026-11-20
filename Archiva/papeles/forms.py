from pathlib import Path

from django import forms
from django.conf import settings

from core.models import Dependencia, Documento, Nivel
from core.forms import Base

from .models import Adenda, AuditoriaInterna, LineaPapel, Marca, PapelTrabajo


class MarcaForm(Base):
    class Meta:
        model = Marca
        fields = ["simbolo", "codigo", "nombre", "significado", "uso"]

    def clean_codigo(self):
        return self.cleaned_data["codigo"].strip().upper()


class AuditoriaForm(Base):
    objetivos = forms.CharField(widget=forms.Textarea(attrs={"rows": 5}), label="Objetivos (uno por línea)",
                                help_text="Quedan fijos al guardar. Solo se modifican mediante adenda.")

    class Meta:
        model = AuditoriaInterna
        fields = ["nombre", "dependencia_auditada"]

    def clean_objetivos(self):
        obj = [x.strip() for x in self.cleaned_data["objetivos"].splitlines() if x.strip()]
        if not obj:
            raise forms.ValidationError("Indique al menos un objetivo.")
        return obj


class AdendaForm(forms.Form):
    objetivo = forms.ModelChoiceField(queryset=None, label="Objetivo a modificar")
    texto_nuevo = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), label="Nuevo texto del objetivo")
    justificacion = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), label="Justificación")

    def __init__(self, auditoria, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["objetivo"].queryset = auditoria.objetivos.all()
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "campo")


class PapelForm(Base):
    class Meta:
        model = PapelTrabajo
        fields = ["codigo", "titulo", "elaborado_por", "supervisado_por"]

    def clean_codigo(self):
        return self.cleaned_data["codigo"].strip().upper()


class LineaForm(Base):
    class Meta:
        model = LineaPapel
        fields = ["concepto", "importe", "documento", "folio", "ref_papel"]

    def __init__(self, *a, docs=None, **kw):
        super().__init__(*a, **kw)
        self.fields["documento"].queryset = docs if docs is not None else Documento.objects.none()
        self.fields["documento"].label = "Documento de respaldo"

    def clean_ref_papel(self):
        return self.cleaned_data["ref_papel"].strip().upper()


class CargaLegajoForm(forms.Form):
    """El tipo de legajo es obligatorio y no tiene valor por defecto."""
    tipo = forms.ChoiceField(choices=[("", "— elija —"), ("LP", "Legajo permanente"), ("LC", "Legajo corriente")], label="Tipo de legajo")
    auditoria = forms.ModelChoiceField(queryset=AuditoriaInterna.objects.all(), required=False, label="Auditoría (solo si es legajo corriente)")
    area = forms.CharField(max_length=8, label="Área o sección (letra o código, ej. C)")
    titulo = forms.CharField(max_length=200, label="Título (el código de archivo se antepone solo)")
    dependencia = forms.ModelChoiceField(queryset=Dependencia.objects.filter(activa=True), label="Dependencia que custodia")
    nivel_acceso = forms.ChoiceField(choices=Nivel.choices, initial=Nivel.DEPENDENCIA, label="Nivel de acceso")
    archivo = forms.FileField(label="Documento escaneado", widget=forms.ClearableFileInput(attrs={"accept": "application/pdf,image/*,.txt"}))

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "campo")

    def clean_archivo(self):
        f = self.cleaned_data["archivo"]
        if Path(f.name).suffix.lower() not in settings.EXTENSIONES_PERMITIDAS:
            raise forms.ValidationError("Formato no permitido. Use PDF, imagen o TXT.")
        if f.size > settings.MAX_UPLOAD_MB * 1024 * 1024:
            raise forms.ValidationError(f"El archivo supera {settings.MAX_UPLOAD_MB} MB.")
        return f

    def clean(self):
        c = super().clean()
        if c.get("tipo") == "LC" and not c.get("auditoria"):
            self.add_error("auditoria", "El legajo corriente debe indicar su auditoría.")
        if c.get("tipo") == "LP":
            c["auditoria"] = None
        return c
