# Simulador Línea de Empaque

Simulación de la línea de acondicionamiento y embalaje para comparar la mesa manual actual
con tres distribuciones de personal usando banda transportadora.

| Distribución | Descripción |
|---|---|
| **A · Mesa manual** | Cada operario hace el proceso completo. Situación actual. |
| **B · Banda lineal, un lado** | Un operario por estación, tareas repartidas en orden. |
| **C · Banda, ambos lados** | El bloque de tareas más pesado se comparte entre 2–3 operarios enfrentados. |
| **D · Celda en U + flotante** | Estaciones fijas y un operario flotante que apoya donde hay cola. |

## 1. Abrir en Visual Studio Code

1. Descomprima la carpeta `simulador_empaque` y ábrala con **Archivo → Abrir carpeta…**
2. Instale las extensiones recomendadas cuando VS Code lo sugiera (Python, Pylance).
3. Abra una terminal (**Terminal → Nueva terminal**) y cree el entorno:

   **Windows (PowerShell)**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
   **macOS / Linux**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
4. Seleccione el intérprete `.venv` (**Ctrl+Shift+P → Python: Select Interpreter**).

Requiere Python 3.10 o superior.

## 2. Ejecutar

Desde la pestaña **Ejecutar y depurar** (Ctrl+Shift+D) hay configuraciones listas:

| Configuración | Qué hace | Comando equivalente |
|---|---|---|
| App interactiva (Streamlit) | Interfaz web con parámetros, comparación, balanceo, sensibilidad y vista de planta animada | `streamlit run app.py` |
| Comparar escenarios | Tabla y gráficas PNG en `salidas/` | `python comparar_escenarios.py --familia solidos --operarios 3 --meta 3600` |
| Comparar todas las familias | 4 familias × 3 y 4 operarios | `python comparar_escenarios.py --todo` |
| Evaluar productos | Proyecta los 471 productos de `datos/tiempos_acond.xlsx` a cada distribución (≈1 min) | `python evaluar_productos.py` |
| Animación de la línea | Ventana con la planta en movimiento | `python -m simulador.animacion --layout C --operarios 4` |

Pruebas: `python -m pytest -q` (o el panel **Testing** de VS Code).

## 3. Estructura

```
simulador_empaque/
├── app.py                    # aplicación Streamlit
├── comparar_escenarios.py    # CLI: compara A-D, exporta Excel y PNG
├── evaluar_productos.py      # CLI: proyección por producto desde el archivo de estándares
├── simulador/
│   ├── familias.py           # familias, tareas de referencia, layouts y Parametros
│   ├── motor.py              # motor de simulación, balanceo, réplicas y calibración
│   ├── estandares.py         # lectura de tiempos_acond.xlsx y proyección por producto
│   ├── graficos.py           # gráficas matplotlib
│   └── animacion.py          # vista de planta (matplotlib y Plotly)
├── datos/tiempos_acond.xlsx  # estándares und/h con 3 personas
├── salidas/                  # resultados generados
└── tests/test_motor.py
```

## 4. Cómo funciona el modelo

- Se simula un turno con paso de 0,25 s: **tiempo efectivo = turno − pausas − despejes** (por defecto 480 − 30 − 20 = 430 min).
- Las tareas de la familia se reparten en estaciones contiguas buscando el **menor cuello de botella** (carga ÷ operarios).
- Entre estaciones la banda tiene **tránsito** (distancia ÷ velocidad) y **capacidad** (distancia ÷ espacio por unidad). Si se llena, el operario anterior queda **bloqueado**.
- Los tiempos varían de forma lognormal (CV 0,25), hay **microparos** (4 por operario-hora, 45 s) y **rechazo** (0,5 %).
- La mesa manual lleva una **sobrecarga** (+35 % por defecto) por tomar/dejar, cambiar de tarea y llevar a embalaje.
- Cada escenario se repite varias veces (réplicas) y se promedian unidades, OEE, uso del tiempo y WIP.

### Calibración

- **Con la producción real**: `calibrar_factor_manual(p, und_turno)` ajusta la sobrecarga manual para que la mesa reproduzca lo que hoy sale por turno.
- **Con un estándar del archivo**: `calibrar_escala(p, und_hora)` escala los tiempos de tarea para que la mesa manual con 3 personas produzca el estándar del producto.
- Lo ideal es reemplazar los tiempos de referencia por **cronometraje** (30 ciclos por tarea) en `simulador/familias.py` o en la app.

### Uso desde código

```python
from simulador import Parametros, comparar, Tarea

p = Parametros(familia="liquidos", operarios=3)
res = comparar(p, reps=5)
for k, r in res.items():
    print(k, round(r["buenas"]), f"OEE {r['oee']:.0%}")

# tareas propias
mis_tareas = [Tarea("Etiquetar", 5.2), Tarea("Estuchar", 7.1), Tarea("Codificar", 3.0), Tarea("Embalar", 2.4)]
res = comparar(Parametros(familia="liquidos", operarios=3, tareas=mis_tareas))
```

## 5. Limitaciones

- Los tiempos por tarea de cada familia son **valores de referencia**; las ganancias calculadas son estimaciones hasta calibrar con datos de planta.
- En `evaluar_productos.py` cada producto se modela con las tareas de su familia escaladas a su estándar; productos con muchos envases por plegadiza o con armado especial pueden diferir.
- No modela abastecimiento de material, cambios de formato ni restricciones de espacio físico.
