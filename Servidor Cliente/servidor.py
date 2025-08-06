# servidor.py

import json
import os
import sqlite3
import signal
import io
import csv
from flask import Flask, jsonify, request, make_response
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # Habilitar CORS para toda la aplicación

# Define la ruta de la base de datos en una variable
DATABASE_PATH = 'contacts.db'

# Función para inicializar la base de datos
def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contactos (
            nombre TEXT PRIMARY KEY,
            telefono TEXT NOT NULL UNIQUE,
            direccion TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# Función para obtener la conexión a la base de datos
def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Esto permite acceder a las columnas por nombre
    return conn

@app.route('/contacts', methods=['GET'])
def get_all_contacts():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    search_term = request.args.get('query')
    
    if search_term:
        cursor.execute(
            'SELECT * FROM contactos WHERE nombre LIKE ? OR telefono LIKE ? OR direccion LIKE ?',
            (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%')
        )
    else:
        cursor.execute('SELECT * FROM contactos')
        
    contactos = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(contactos)

@app.route('/contacts', methods=['POST'])
def add_contact():
    data = request.get_json()
    nombre = data.get('nombre')
    telefono = data.get('telefono')
    direccion = data.get('direccion')

    if not all([nombre, telefono, direccion]):
        return jsonify({'error': 'Faltan datos obligatorios'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM contactos WHERE telefono = ?", (telefono,))
    if cursor.fetchone()[0] > 0:
        conn.close()
        return jsonify({'error': f'Ya existe un contacto con el teléfono "{telefono}".'}), 409

    try:
        cursor.execute("INSERT INTO contactos (nombre, telefono, direccion) VALUES (?, ?, ?)",
                       (nombre, telefono, direccion))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': f'El contacto con nombre "{nombre}" ya existe.'}), 409
    finally:
        conn.close()
    
    return jsonify({'message': f'Contacto "{nombre}" agregado exitosamente.'}), 201

@app.route('/contacts/<nombre>', methods=['PUT'])
def update_contact(nombre):
    data = request.get_json()
    telefono = data.get('telefono')
    direccion = data.get('direccion')

    if not telefono and not direccion:
        return jsonify({'error': 'Se requiere al menos el teléfono o la dirección para actualizar'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if telefono:
        cursor.execute("SELECT COUNT(*) FROM contactos WHERE telefono = ? AND nombre != ?", (telefono, nombre))
        if cursor.fetchone()[0] > 0:
            conn.close()
            return jsonify({'error': f'Ya existe otro contacto con el teléfono "{telefono}".'}), 409
            
    query_parts = []
    params = []
    if telefono:
        query_parts.append("telefono = ?")
        params.append(telefono)
    if direccion:
        query_parts.append("direccion = ?")
        params.append(direccion)
        
    set_clause = ", ".join(query_parts)
    params.append(nombre)
    
    cursor.execute(f"UPDATE contactos SET {set_clause} WHERE nombre = ?", tuple(params))
    conn.commit()
    
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({'error': f'Contacto "{nombre}" no encontrado.'}), 404
        
    conn.close()
    return jsonify({'message': f'Contacto "{nombre}" actualizado exitosamente.'}), 200

@app.route('/contacts/<nombre>', methods=['DELETE'])
def delete_contact(nombre):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM contactos WHERE nombre = ?", (nombre,))
    conn.commit()
    
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({'error': f'Contacto "{nombre}" no encontrado.'}), 404
        
    conn.close()
    return jsonify({'message': f'Contacto "{nombre}" eliminado exitosamente.'}), 200

@app.route('/enviar_mensaje', methods=['POST'])
def recibir_mensaje():
    data = request.json
    mensaje = data.get('mensaje')
    if not mensaje:
        return jsonify({'status': 'error', 'message': 'Mensaje no proporcionado'}), 400

    print(f"Mensaje recibido: {mensaje}")
    return jsonify({'status': 'success', 'message': 'Mensaje recibido, gracias por el reporte.'})

@app.route('/shutdown', methods=['POST'])
def shutdown():
    print("Apagando el servidor...")
    os.kill(os.getpid(), signal.SIGINT)
    return jsonify({'response': 'Servidor apagado'}), 200

@app.route('/export', methods=['GET'])
def export_contacts():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT nombre, telefono, direccion FROM contactos')
    contacts = cursor.fetchall()
    conn.close()

    si = io.StringIO(newline='')
    cw = csv.writer(si)
    
    cw.writerow(['nombre', 'telefono', 'direccion'])
    
    cw.writerows(contacts)
    
    output = make_response(si.getvalue())
    output.headers['Content-Disposition'] = 'attachment; filename=contacts.csv'
    output.headers['Content-type'] = 'text/csv; charset=utf-8' 
    
    return output

@app.route('/import', methods=['POST'])
def import_contacts():
    if 'text/csv' not in request.headers['Content-Type']:
        return jsonify({'error': 'Tipo de contenido no soportado. Se espera text/csv'}), 415

    csv_data = request.data.decode('utf-8')
    si = io.StringIO(csv_data)
    reader = csv.reader(si)
    
    try:
        header = next(reader)
        if [h.strip() for h in header] != ['nombre', 'telefono', 'direccion']:
            return jsonify({'error': 'La cabecera del archivo CSV no es válida. Se esperaba: nombre,telefono,direccion'}), 400
    except StopIteration:
        return jsonify({'error': 'El archivo CSV está vacío.'}), 400
        
    imported_count = 0
    errors = []

    conn = get_db_connection()
    cursor = conn.cursor()
    
    for row in reader:
        try:
            nombre, telefono, direccion = row
            cursor.execute("INSERT INTO contactos (nombre, telefono, direccion) VALUES (?, ?, ?)",
                           (nombre.strip(), telefono.strip(), direccion.strip()))
            imported_count += 1
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: contactos.nombre" in str(e):
                errors.append(f"Error: El contacto '{nombre}' ya existe.")
            elif "UNIQUE constraint failed: contactos.telefono" in str(e):
                errors.append(f"Error: El teléfono '{telefono}' ya existe para otro contacto.")
            else:
                errors.append(f"Error desconocido al importar el contacto '{nombre}': {e}")
        except ValueError:
            errors.append(f"Error: La fila '{row}' no tiene el formato correcto (debe tener 3 columnas).")

    conn.commit()
    conn.close()
    
    if errors:
        error_message = f"Se importaron {imported_count} contactos. Ocurrieron errores en la importación:\n" + "\n".join(errors)
        return jsonify({'error': error_message}), 400
    else:
        return jsonify({'message': f'Se importaron {imported_count} contactos exitosamente.'})

if __name__ == '__main__':
    init_db()
    app.run(debug=True)