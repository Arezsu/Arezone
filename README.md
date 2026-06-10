# AREZONE POS

AREZONE es un POS local para Windows, con SQLite, temas grandes, ventas, inventario, reportes e impresion directa.

## Arranque

- `2_ABRIR_AREZONE.bat` abre la app en desarrollo.
- `3_COMPILAR_INSTALADOR.bat` genera el ejecutable y el instalador.

## Flujo inicial

1. Si no hay tienda registrada, aparece el registro inicial.
2. Si ya hay tienda, entra directo al login.
3. Todo queda guardado localmente en SQLite.

## Datos

- Tienda
- Usuarios
- Productos
- Ventas
- Facturas
- Configuracion

## Impresion

- Facturas en `Documentos\AREZONE\Facturas`
- Impresion RAW directa
- Cajon de dinero soportado por configuracion de impresora

## Notas

- No usa servidor externo.
- No usa validacion externa.
- No depende de archivos `.txt` remotos.
