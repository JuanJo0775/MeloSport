#!/usr/bin/env bash
# build.sh
# Script de construcción y configuración automática para Render

set -o errexit  # Si ocurre un error, detiene el proceso inmediatamente

echo "🚀 Iniciando build en Render..."

# ================================
# 1️⃣ Instalar dependencias
# ================================
pip install --upgrade pip
pip install -r requirements.txt

# ================================
# 2️⃣ Aplicar migraciones de base de datos
# ================================
echo "📦 Ejecutando migraciones..."
python manage.py migrate --noinput

# ================================
# 3️⃣ Recolectar archivos estáticos
# ================================
echo "🎨 Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

# ================================
# 4️⃣ Crear roles y superusuario inicial (comando personalizado)
# ================================
echo "👤 Creando roles y superusuario (init_roles.py)..."
python manage.py init_roles

echo "✅ Configuración completada correctamente."
