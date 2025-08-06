# cliente.py

import sys
import requests
import os
import csv
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLineEdit,
                             QPushButton, QHBoxLayout, QTextEdit, QDialog,
                             QLabel, QMessageBox, QTableWidget, QTableWidgetItem,
                             QHeaderView, QFileDialog)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import QUrl, QFile, QTextStream
from PyQt6.QtGui import QCloseEvent

class ClientController:
    def __init__(self, server_url='http://127.0.0.1:5000'):
        self.server_url = server_url

    def get_all_contacts(self):
        """Obtiene todos los contactos del servidor."""
        try:
            response = requests.get(f'{self.server_url}/contacts')
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'error': f'Error al obtener contactos: {e}'}

    def search_contact(self, query: str):
        """Busca contactos por nombre, teléfono o dirección."""
        try:
            response = requests.get(f'{self.server_url}/contacts', params={'query': query})
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return {'error': f'No se encontraron contactos que coincidan con "{query}".'}
            return {'error': f'Error HTTP: {e.response.status_code}'}
        except requests.exceptions.RequestException as e:
            return {'error': f'Error de conexión: {e}'}

    def add_contact(self, nombre: str, telefono: str, direccion: str):
        """Agrega un nuevo contacto."""
        data = {'nombre': nombre, 'telefono': telefono, 'direccion': direccion}
        try:
            response = requests.post(f'{self.server_url}/contacts', json=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_message = e.response.json().get('error', f'Error HTTP: {e.response.status_code}')
            return {'error': f'Error al agregar contacto: {error_message}'}
        except requests.exceptions.RequestException as e:
            return {'error': f'Error de conexión: {e}'}

    def delete_contact(self, nombre: str):
        """Elimina un contacto por nombre."""
        try:
            response = requests.delete(f'{self.server_url}/contacts/{nombre}')
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return {'error': f'Contacto "{nombre}" no encontrado.'}
            return {'error': f'Error HTTP: {e.response.status_code}'}
        except requests.exceptions.RequestException as e:
            return {'error': f'Error de conexión: {e}'}

    def update_contact(self, nombre: str, telefono: str, direccion: str):
        """Actualiza un contacto existente."""
        data = {}
        if telefono:
            data['telefono'] = telefono
        if direccion:
            data['direccion'] = direccion
        
        try:
            response = requests.put(f'{self.server_url}/contacts/{nombre}', json=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_message = e.response.json().get('error', f'Error HTTP: {e.response.status_code}')
            return {'error': f'Error al actualizar contacto: {error_message}'}
        except requests.exceptions.RequestException as e:
            return {'error': f'Error de conexión: {e}'}
            
    def send_message(self, mensaje: str):
        """Envía un mensaje al servidor."""
        url = f'{self.server_url}/enviar_mensaje'
        try:
            response = requests.post(url, json={'mensaje': mensaje})
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'status': 'error', 'message': f'Error de conexión: {e}'}
            
    def shutdown_server(self):
        """Envía una petición de apagado al servidor."""
        try:
            requests.post(f'{self.server_url}/shutdown')
        except requests.exceptions.RequestException as e:
            print(f"Error al enviar la señal de apagado al servidor: {e}")

    def export_contacts(self):
        """Solicita al servidor que exporte todos los contactos."""
        try:
            response = requests.get(f'{self.server_url}/export', timeout=30)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            return {'error': f'Error al exportar contactos: {e}'}

    def import_contacts(self, contacts_csv: str):
        """Envía al servidor un string en formato CSV para importar contactos."""
        try:
            response = requests.post(f'{self.server_url}/import', data=contacts_csv, headers={'Content-Type': 'text/csv'})
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_message = ""
            if e.response is not None:
                try:
                    error_message = e.response.json().get('error', f'Error HTTP: {e.response.status_code}')
                except json.JSONDecodeError:
                    error_message = f'Error HTTP: {e.response.status_code}'
            return {'error': f'Error al importar contactos: {error_message}'}


class MessageDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reportar un Problema")
        self.controller = controller
        self.parent_window = parent

        self.layout = QVBoxLayout()

        self.label = QLabel("Describe tu problema o sugerencia:")
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("Escribe tu mensaje aquí...")
        self.send_button = QPushButton("Enviar Mensaje")
        self.send_button.clicked.connect(self.send_message)
        
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.text_input)
        self.layout.addWidget(self.send_button)
        self.setLayout(self.layout)

    def send_message(self):
        message = self.text_input.toPlainText().strip()
        if not message:
            QMessageBox.warning(self, "Error de Validación", "El mensaje no puede estar vacío.")
            return

        response = self.controller.send_message(message)
        
        if response.get('status') == 'success':
            QMessageBox.information(self, "Mensaje Enviado", response.get('message'))
            self.parent_window.mostrar_video_agradecimiento()
            self.close()
        else:
            QMessageBox.critical(self, "Error de Envío", f"Error: {response.get('message', 'Error desconocido')}")

class UpdateContactDialog(QDialog):
    def __init__(self, controller, contact_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Actualizar Contacto: {contact_name}")
        self.controller = controller
        self.contact_name = contact_name
        self.parent_window = parent

        self.layout = QVBoxLayout()
        
        self.label_telefono = QLabel("Nuevo Teléfono:")
        self.input_telefono = QLineEdit()
        self.input_telefono.setPlaceholderText("Ingresa el nuevo teléfono")
        
        self.label_direccion = QLabel("Nueva Dirección:")
        self.input_direccion = QLineEdit()
        self.input_direccion.setPlaceholderText("Ingresa la nueva dirección")
        
        self.update_button = QPushButton("Actualizar Contacto")
        self.update_button.clicked.connect(self.update_contact)
        
        self.layout.addWidget(self.label_telefono)
        self.layout.addWidget(self.input_telefono)
        self.layout.addWidget(self.label_direccion)
        self.layout.addWidget(self.input_direccion)
        self.layout.addWidget(self.update_button)
        
        self.setLayout(self.layout)

    def update_contact(self):
        telefono = self.input_telefono.text().strip()
        direccion = self.input_direccion.text().strip()

        if not telefono and not direccion:
            QMessageBox.warning(self, "Error de Validación", "Debes ingresar al menos el teléfono o la dirección para actualizar.")
            return

        response = self.controller.update_contact(self.contact_name, telefono, direccion)

        if 'error' in response:
            QMessageBox.critical(self, "Error de Actualización", f"ERROR: {response['error']}")
        else:
            QMessageBox.information(self, "Actualización Exitosa", f"Contacto {self.contact_name} actualizado correctamente.")
            self.parent_window.get_all_contacts()
            self.close()

class ClientApp(QWidget):
    def __init__(self):
        super().__init__()
        self.controller = ClientController()
        
        self.setWindowTitle('Agenda de Contactos Conased')
        self.setGeometry(100, 100, 800, 500)
        
        self.load_stylesheet()

        self.layout = QVBoxLayout()
        
        self.input_nombre = QLineEdit(self)
        self.input_nombre.setPlaceholderText('Nombre')
        self.input_telefono = QLineEdit(self)
        self.input_telefono.setPlaceholderText('Teléfono')
        self.input_direccion = QLineEdit(self)
        self.input_direccion.setPlaceholderText('Dirección')
        self.add_button = QPushButton('Agregar Contacto')
        self.add_button.clicked.connect(self.add_contact)
        
        add_layout = QHBoxLayout()
        add_layout.addWidget(self.input_nombre)
        add_layout.addWidget(self.input_telefono)
        add_layout.addWidget(self.input_direccion)
        add_layout.addWidget(self.add_button)

        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText('Buscar por nombre, teléfono o dirección')
        self.search_button = QPushButton('Buscar')
        self.search_button.clicked.connect(self.search_contact)
        self.delete_button = QPushButton('Eliminar')
        self.delete_button.clicked.connect(self.delete_contact)
        
        self.update_button = QPushButton('Actualizar')
        self.update_button.clicked.connect(self.show_update_dialog)
        
        search_layout = QHBoxLayout()
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)
        search_layout.addWidget(self.delete_button)
        search_layout.addWidget(self.update_button)

        self.get_all_button = QPushButton('Mostrar todos los contactos')
        self.get_all_button.clicked.connect(self.get_all_contacts)
        
        self.report_button = QPushButton("Reportar un Problema")
        self.report_button.clicked.connect(self.show_message_dialog)

        self.export_button = QPushButton("Exportar a CSV")
        self.export_button.clicked.connect(self.export_contacts_to_file)
        self.import_button = QPushButton("Importar desde CSV")
        self.import_button.clicked.connect(self.import_contacts_from_file)
        
        file_io_layout = QHBoxLayout()
        file_io_layout.addWidget(self.export_button)
        file_io_layout.addWidget(self.import_button)

        self.table_widget = QTableWidget(self)
        self.table_widget.setColumnCount(3)
        self.table_widget.setHorizontalHeaderLabels(['Nombre', 'Teléfono', 'Dirección'])
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        self.table_widget.cellDoubleClicked.connect(self.open_update_dialog_from_table)

        self.layout.addLayout(add_layout)
        self.layout.addLayout(search_layout)
        self.layout.addLayout(file_io_layout)
        self.layout.addWidget(self.get_all_button)
        self.layout.addWidget(self.report_button)
        self.layout.addWidget(self.table_widget)
        
        self.setLayout(self.layout)
        
        self.get_all_contacts()
    
    def load_stylesheet(self):
        style_file = QFile(os.path.join(os.path.dirname(__file__), 'style.qss'))
        if style_file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
            stream = QTextStream(style_file)
            self.setStyleSheet(stream.readAll())
            style_file.close()

    def closeEvent(self, event: QCloseEvent):
        self.controller.shutdown_server()
        event.accept()

    def show_message(self, title, message, icon):
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setIcon(icon)
        msg.exec()

    def add_contact(self):
        nombre = self.input_nombre.text().strip()
        telefono = self.input_telefono.text().strip()
        direccion = self.input_direccion.text().strip()
        
        if not nombre or not telefono or not direccion:
            self.show_message("Error de Validación", "Todos los campos (nombre, teléfono, dirección) son obligatorios.", QMessageBox.Icon.Warning)
            return

        response = self.controller.add_contact(nombre, telefono, direccion)
        if 'error' in response:
            self.show_message("Error al Agregar", response['error'], QMessageBox.Icon.Critical)
        else:
            self.show_message("Éxito", f"Contacto '{nombre}' agregado correctamente.", QMessageBox.Icon.Information)
            self.get_all_contacts()

    def search_contact(self):
        query = self.search_input.text().strip()
        if query:
            response = self.controller.search_contact(query)
            self.display_response(response)
        else:
            self.get_all_contacts()

    def delete_contact(self):
        nombre = self.search_input.text().strip()
        if not nombre:
            self.show_message("Error de Validación", "Por favor, ingrese un nombre para eliminar.", QMessageBox.Icon.Warning)
            return
            
        reply = QMessageBox.question(self, 'Confirmar Eliminación', 
                                     f"¿Estás seguro de que quieres eliminar el contacto '{nombre}'?", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                     QMessageBox.StandardButton.No)
                                     
        if reply == QMessageBox.StandardButton.Yes:
            response = self.controller.delete_contact(nombre)
            if 'error' in response:
                self.show_message("Error al Eliminar", response['error'], QMessageBox.Icon.Critical)
            else:
                self.show_message("Éxito", response['message'], QMessageBox.Icon.Information)
                self.get_all_contacts()

    def show_update_dialog(self):
        nombre = self.search_input.text().strip()
        if not nombre:
            self.show_message("Error de Validación", "Por favor, ingrese un nombre para actualizar.", QMessageBox.Icon.Warning)
            return
        
        search_result = self.controller.search_contact(nombre)
        if 'error' in search_result:
            self.show_message("Contacto No Encontrado", search_result['error'], QMessageBox.Icon.Critical)
        else:
            dialog = UpdateContactDialog(self.controller, nombre, self)
            dialog.exec()
            
    def open_update_dialog_from_table(self, row, column):
        item = self.table_widget.item(row, 0)
        if item:
            contact_name = item.text()
            dialog = UpdateContactDialog(self.controller, contact_name, self)
            dialog.exec()

    def get_all_contacts(self):
        response = self.controller.get_all_contacts()
        self.display_response(response)

    def show_message_dialog(self):
        dialog = MessageDialog(self.controller, self)
        dialog.exec()
        
    def mostrar_video_agradecimiento(self):
        dialogo_video = QDialog(self)
        dialogo_video.setWindowTitle("Mensaje Recibido")
        dialogo_video.setFixedSize(800, 600)
        layout_video = QVBoxLayout()

        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        
        video_widget = QVideoWidget()
        self.media_player.setVideoOutput(video_widget)
        
        video_path = r"C:\Users\messi\Desktop\conased\respuesta.mp4"
        
        self.media_player.setSource(QUrl.fromLocalFile(video_path))
        
        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.clicked.connect(dialogo_video.close)
        
        dialogo_video.finished.connect(self.detener_video)

        layout_video.addWidget(video_widget)
        layout_video.addWidget(boton_cerrar)
        dialogo_video.setLayout(layout_video)

        self.media_player.play()
        dialogo_video.exec()
        
    def detener_video(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.stop()

    def display_response(self, response):
        self.table_widget.setRowCount(0)

        if 'error' in response:
            self.show_message("Error", response["error"], QMessageBox.Icon.Critical)
        elif isinstance(response, list):
            self.table_widget.setRowCount(len(response))
            for i, contact in enumerate(response):
                self.table_widget.setItem(i, 0, QTableWidgetItem(contact.get('nombre', '')))
                self.table_widget.setItem(i, 1, QTableWidgetItem(contact.get('telefono', '')))
                self.table_widget.setItem(i, 2, QTableWidgetItem(contact.get('direccion', '')))
        elif 'message' in response:
            self.show_message("Información", response["message"], QMessageBox.Icon.Information)
        else:
            self.show_message("Información", str(response), QMessageBox.Icon.Information)
            
    def export_contacts_to_file(self):
        """Maneja la lógica de exportar contactos."""
        response = self.controller.export_contacts()
        if 'error' in response:
            self.show_message("Error de Exportación", response['error'], QMessageBox.Icon.Critical)
            return

        file_dialog = QFileDialog(self)
        file_path, _ = file_dialog.getSaveFileName(self, "Guardar contactos", "contacts.csv", "Archivos CSV (*.csv)")

        if file_path:
            try:
                with open(file_path, 'w', newline='', encoding='utf-8') as file:
                    file.write(response)
                self.show_message("Exportación Exitosa", f"Contactos exportados a:\n{file_path}", QMessageBox.Icon.Information)
            except Exception as e:
                self.show_message("Error de Archivo", f"No se pudo guardar el archivo: {e}", QMessageBox.Icon.Critical)

    def import_contacts_from_file(self):
        """Maneja la lógica de importar contactos."""
        file_dialog = QFileDialog(self)
        file_path, _ = file_dialog.getOpenFileName(self, "Seleccionar archivo para importar", "", "Archivos CSV (*.csv)")

        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    contacts_csv_data = file.read()
                
                response = self.controller.import_contacts(contacts_csv_data)
                
                if 'error' in response:
                    self.show_message("Error de Importación", response['error'], QMessageBox.Icon.Critical)
                else:
                    self.show_message("Importación Exitosa", response['message'], QMessageBox.Icon.Information)
                    self.get_all_contacts()
            except Exception as e:
                self.show_message("Error de Archivo", f"No se pudo leer el archivo: {e}", QMessageBox.Icon.Critical)


def run_client():
    app = QApplication(sys.argv)
    window = ClientApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    run_client()