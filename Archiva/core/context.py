"""Menú de navegación compartido por escritorio (barra lateral) y móvil (menú desplegable + barra inferior)."""
from .services import rol_de
from .models import Rol

ICONOS = {
    "panel": "M3 12l9-9 9 9M5 10v10h14V10",
    "documentos": "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z M14 3v5h5 M9 13h6 M9 17h6",
    "correspondencia": "M3 6h18v12H3z M3 7l9 6 9-6",
    "expedientes": "M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
    "tramites": "M5 12h14 M13 6l6 6-6 6",
    "fisico": "M3 4h18v4H3z M5 8v11h14V8 M10 12h4",
    "buscar": "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14z M20 20l-4-4",
    "reportes": "M4 20V4 M4 20h16 M8 16v-5 M12 16V8 M16 16v-8",
    "auditoria": "M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z M9 12l2 2 4-4",
    "papeles": "M9 3h9a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H9 M9 3v18 M4 7h5 M4 12h5 M4 17h5 M13 9h4 M13 13h4",
}

# (clave, etiqueta, url_name, prefijo de ruta para marcar activo, roles permitidos o None, visible en barra inferior móvil)
ITEMS = [
    ("panel", "Panel principal", "dashboard", "/", None, True),
    ("buscar", "Buscar", "busqueda", "/buscar/", None, True),
    ("documentos", "Documentos", "documentos", "/documentos/", None, True),
    ("expedientes", "Expedientes", "expedientes", "/expedientes/", None, False),
    ("correspondencia", "Correspondencia", "correspondencia", "/correspondencia/", None, False),
    ("tramites", "Trámites", "tramites", "/tramites/", None, True),
    ("fisico", "Archivo físico", "archivo_fisico", "/archivo-fisico/", None, False),
    ("reportes", "Reportes", "reportes", "/reportes/", None, False),
    ("papeles", "Papeles de trabajo (UAI)", "uai_inicio", "/uai/", (Rol.ADMIN, Rol.AUDITOR, Rol.ARCHIVISTA), False),
    ("auditoria", "Auditoría y seguridad", "auditoria", "/auditoria/", (Rol.ADMIN, Rol.AUDITOR), False),
]


def navegacion(request):
    if not request.user.is_authenticated:
        return {}
    rol = rol_de(request.user)
    ruta = request.path
    items = []
    for clave, etiqueta, url, prefijo, roles, barra in ITEMS:
        if roles and rol not in roles:
            continue
        activo = ruta == "/" if prefijo == "/" else ruta.startswith(prefijo)
        items.append({"clave": clave, "label": etiqueta, "corto": "Inicio" if clave == "panel" else etiqueta, "url": url, "d": ICONOS[clave], "activo": activo, "barra": barra})
    perfil = getattr(request.user, "perfil", None)
    return {"nav_items": items, "mi_rol": perfil.get_rol_display() if perfil else "Administrador",
            "mi_dependencia": perfil.dependencia.sigla if perfil and perfil.dependencia else "",
            "iniciales": (request.user.get_full_name() or request.user.username)[:2].upper()}
