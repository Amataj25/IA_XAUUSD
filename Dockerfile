# Usa una imagen base de Python
FROM python:3.12

# Establece el directorio de trabajo
WORKDIR /app

# Copia todos los archivos y directorios del proyecto al contenedor
COPY . .

# Establece el directorio de trabajo para el script
WORKDIR /app/scripts

# Instala las dependencias
RUN pip install --upgrade pip
RUN pip install numpy

# Comando para ejecutar tu script
CMD ["python", "automated_trading.py"]
