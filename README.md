# 🤖 sii_bot

Automatización de la Declaración F29 sin movimiento para empresas chilenas que no están operando actualmente.

## 🚀 ¿Qué hace este bot?

Este script automatiza la declaración mensual del Formulario 29 (F29) en el sitio web del SII para empresas sin movimientos. Está pensado para evitar multas por no declarar a tiempo, incluso cuando la empresa no haya tenido actividad en el mes. Ideal para empresas inactivas que deben cumplir con esta obligación igual.


> Yo mismo, como fundador de una SPA, olvidé realizar esta declaración dos veces y tuve que pagar multas innecesarias. Esto automatiza por completo ese proceso tan simple, pero fácil de olvidar.

![Demostración de funcionamiento del bot](run%20sii%20bot.gif)

## 🔧 Requisitos

- Python 3.8 o superior
- Google Chrome instalado (recomendado última versión disponible)
- Credenciales de acceso al SII
- Sistema operativo Windows, macOS o Linux

## 📦 Instalación y uso

1. Clona este repositorio:

```bash
git clone https://github.com/rodolflying/sii_bot.git
cd sii_bot
```


2. Cambia el nombre del archivo env a .env y escribe tus credenciales de empresa

USER_NAME_SPA=12345678-9
PASSWORD_SPA=miclave

3. Instala las dependencias:

```bash
pip install -r requirements.txt
```

4. Ejecuta el bot:

```bash
python main.py
```

## 📁 Archivos generados


El script descargará automáticamente el certificado PDF si el mes no ha sido declarado y lo renombrará como `Formulario_29_mes_año.pdf`. También registrará la declaración en un archivo CSV para control. Todo en la carpeta creada automáticamente llamada "declaraciones"


## 💡 Nota importante
Solo funciona para declaraciones F29 sin movimientos. Si tu empresa tiene gastos o ventas que declarar, este script no es para ti (aún 😉).

Se está trabajando en una versión futura que permita incluir movimientos y declarar montos reales.

## 🤝 Contacto
¿Dudas o sugerencias?
Puedes contactarme directamente en [LinkedIn](https://www.linkedin.com/in/rodolfo-sepulveda-847532135/)
