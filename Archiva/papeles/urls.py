from django.urls import path

from . import views as v

urlpatterns = [
    path("uai/", v.inicio, name="uai_inicio"),
    path("uai/marcas/", v.marcas, name="uai_marcas"),
    path("uai/marcas/nueva/", v.marca_nueva, name="uai_marca_nueva"),
    path("uai/marcas/<int:pk>/retirar/", v.marca_retirar, name="uai_marca_retirar"),
    path("uai/legajo-permanente/", v.legajo_permanente, name="uai_legajo_permanente"),
    path("uai/cargar/", v.documento_cargar, name="uai_cargar"),
    path("uai/auditorias/nueva/", v.auditoria_nueva, name="uai_auditoria_nueva"),
    path("uai/auditorias/<int:pk>/", v.auditoria, name="uai_auditoria"),
    path("uai/auditorias/<int:pk>/adenda/", v.adenda_nueva, name="uai_adenda_nueva"),
    path("uai/auditorias/<int:pk>/papel/", v.papel_nuevo, name="uai_papel_nuevo"),
    path("uai/auditorias/<int:pk>/verificador/", v.verificador, name="uai_verificador"),
    path("uai/auditorias/<int:pk>/informe/", v.informe, name="uai_informe"),
    path("uai/auditorias/<int:pk>/libro.xlsx", v.libro, name="uai_libro"),
    path("uai/papeles/<int:pk>/", v.papel, name="uai_papel"),
    path("uai/papeles/<int:pk>/linea/", v.linea_nueva, name="uai_linea_nueva"),
    path("uai/papeles/<int:pk>/sugerir/", v.papel_sugerir, name="uai_papel_sugerir"),
    path("uai/papeles/<int:pk>/descargar/<str:formato>/", v.papel_descargar, name="uai_papel_descargar"),
    path("uai/lineas/<int:pk>/confirmar/", v.linea_confirmar, name="uai_linea_confirmar"),
    path("uai/lineas/<int:pk>/rechazar/", v.linea_rechazar, name="uai_linea_rechazar"),
]
