"""Familias de producto, distribuciones (layouts) y parámetros por defecto.

Los tiempos por tarea son VALORES DE REFERENCIA (segundos por unidad de venta).
Reemplácelos por los cronometrados en planta, o calíbrelos con el estándar real
usando `simulador.estandares`.
"""
from dataclasses import dataclass, field, asdict


@dataclass
class Tarea:
    nombre: str
    t: float  # segundos estándar por unidad


FAMILIAS = {
    "solidos": {
        "nombre": "Sólidos (blíster)", "unidad": "estuche",
        "tareas": [
            Tarea("Armar estuche", 4.0),
            Tarea("Insertar blísteres", 5.0),
            Tarea("Insertar prospecto", 3.5),
            Tarea("Cerrar estuche", 3.0),
            Tarea("Codificar lote/venc. y verificar", 3.5),
            Tarea("Embalar en corrugado", 2.5),
        ],
    },
    "liquidos": {
        "nombre": "Líquidos (frasco)", "unidad": "estuche",
        "tareas": [
            Tarea("Inspeccionar frasco", 2.5),
            Tarea("Etiquetar frasco", 6.0),
            Tarea("Armar estuche", 4.0),
            Tarea("Insertar frasco, prospecto y dosificador", 6.5),
            Tarea("Cerrar y codificar", 4.5),
            Tarea("Embalar en corrugado", 3.0),
        ],
    },
    "semisolidos": {
        "nombre": "Semisólidos (tubo)", "unidad": "estuche",
        "tareas": [
            Tarea("Codificar tubo", 3.0),
            Tarea("Armar estuche", 4.0),
            Tarea("Insertar tubo y prospecto", 5.0),
            Tarea("Cerrar estuche", 3.0),
            Tarea("Codificar estuche y verificar", 3.5),
            Tarea("Embalar en corrugado", 2.5),
        ],
    },
    "sobres": {
        "nombre": "Sobres (display x10)", "unidad": "display",
        "tareas": [
            Tarea("Contar e inspeccionar 10 sobres", 7.0),
            Tarea("Armar display", 4.0),
            Tarea("Llenar display", 6.0),
            Tarea("Cerrar y codificar display", 4.5),
            Tarea("Agrupar / termoencoger", 3.0),
            Tarea("Embalar en corrugado", 3.0),
        ],
    },
}

# Forma farmacéutica del archivo de estándares -> familia del simulador
FORMA_A_FAMILIA = {
    "TAB": "solidos", "CAP": "solidos",
    "LIQ": "liquidos", "JBE": "liquidos", "FRASCO": "liquidos",
    "CRE": "semisolidos",
    "POL": "sobres",
}

LAYOUTS = {
    "A": {"nombre": "A · Mesa manual (actual)", "corto": "Mesa manual", "banda": False, "flex": False, "doble_lado": False,
          "descripcion": "Cada operario hace el proceso completo en su puesto. Sin banda."},
    "B": {"nombre": "B · Banda lineal, un lado", "corto": "Banda lineal", "banda": True, "flex": False, "doble_lado": False,
          "descripcion": "Banda recta, un operario por estación, tareas repartidas en orden."},
    "C": {"nombre": "C · Banda, ambos lados", "corto": "Ambos lados", "banda": True, "flex": False, "doble_lado": True,
          "descripcion": "Puestos a lado y lado; el bloque más pesado se comparte entre 2-3 operarios enfrentados."},
    "D": {"nombre": "D · Celda en U + flotante", "corto": "U + flotante", "banda": True, "flex": True, "doble_lado": False,
          "descripcion": "Banda en U con estaciones fijas y un operario flotante que apoya la estación con más cola."},
}


@dataclass
class Parametros:
    familia: str = "solidos"
    layout: str = "B"
    operarios: int = 4
    turno_min: float = 480      # duración del turno
    pausas_min: float = 30      # pausas y alimentación
    despejes: int = 1           # despejes de línea por turno
    despeje_min: float = 20     # duración de cada despeje
    cv: float = 0.25            # coeficiente de variación de los tiempos
    factor_manual: float = 1.35  # sobrecarga de la mesa manual (tomar/dejar, cambio de tarea, transporte)
    factor_banda: float = 1.00   # factor en banda (colocar en banda vs. especialización)
    paro_hora: float = 4         # microparos por operario-hora
    paro_seg: float = 45         # duración media de un microparo (s)
    rechazo: float = 0.5         # % rechazo en inspección
    dist_est: float = 1.2        # m entre estaciones
    vel_banda: float = 6         # m/min
    paso: float = 0.15           # m que ocupa cada unidad en la banda
    caminar_seg: float = 3       # s que tarda el flotante en cambiar de estación
    semilla: int = 1
    tareas: list = field(default=None)  # lista de Tarea; None = las de la familia
    escala_tiempos: float = 1.0  # multiplica todos los tiempos de tarea (calibración por producto)

    def copia(self, **cambios):
        d = asdict(self)
        d["tareas"] = self.tareas
        d.update(cambios)
        return Parametros(**d)

    def lista_tareas(self):
        base = self.tareas if self.tareas else FAMILIAS[self.familia]["tareas"]
        return [Tarea(t.nombre, t.t * self.escala_tiempos) for t in base]

    @property
    def efectivo_seg(self):
        return (self.turno_min - self.pausas_min - self.despejes * self.despeje_min) * 60

    @property
    def horas_plan(self):
        return (self.turno_min - self.pausas_min) / 60
