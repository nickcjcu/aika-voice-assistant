
import os
import sys
import platform
import subprocess

from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePermission

from token_server import start_chat_server


# Application settings

APP_NAME = "AIKA+"

WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 700

SIDEBAR_WIDTH = 220

BACKGROUND = "#171A1F"
SIDEBAR_BACKGROUND = "#20242B"
PANEL_BACKGROUND = "#1C2026"

ACCENT = "#54C7B5"

TEXT = "#F2F4F7"
SECONDARY_TEXT = "#929BA8"

BORDER = "#343A43"
ERROR_COLOUR = "#F07878"

PROJECT_ROOT = Path(__file__).resolve().parent.parent

AGENT_FILE = PROJECT_ROOT / "src" / "main.py"


# Application stylesheet

STYLESHEET = """

QMainWindow {
    background-color: #171A1F;
    font-family: "Segoe UI";
}

QWidget {
    color: #F2F4F7;
    font-family: "Segoe UI";
    font-size: 13px;
}

QFrame#sidebar {
    background-color: #20242B;
    border-radius: 12px;
}

QFrame#main_panel {
    background-color: #1C2026;
    border-radius: 12px;
}

QLabel#logo {
    color: #54C7B5;
    font-size: 30px;
    font-weight: bold;
}

QLabel#subtitle {
    color: #929BA8;
    font-size: 12px;
}

QLabel#section_label {
    color: #929BA8;
    font-size: 11px;
    font-weight: bold;
}

QLabel#status_label {
    font-size: 13px;
    font-weight: bold;
}

QPushButton {
    background-color: #343A43;
    color: #F2F4F7;
    border: none;
    border-radius: 7px;
    padding: 10px;
}

QPushButton:hover {
    background-color: #414955;
}

QPushButton:disabled {
    color: #707985;
    background-color: #292F38;
}

QPushButton#start_button {
    background-color: #54C7B5;
    color: #171A1F;
    font-weight: bold;
}

QPushButton#start_button:hover {
    background-color: #6BD8C7;
}

QPushButton#output_toggle_button {
    background-color: transparent;
    color: #929BA8;
    font-size: 13px;
    padding: 2px;
}

QPushButton#output_toggle_button:hover {
    color: #54C7B5;
    background-color: #292F38;
}

QPlainTextEdit#log_output {
    background-color: #171A1F;
    color: #929BA8;
    border: 1px solid #343A43;
    border-radius: 7px;
    padding: 8px;
    font-family: Consolas, monospace;
    font-size: 11px;
}

QWebEngineView {
    background-color: #1C2026;
    border: none;
    border-radius: 8px;
}

"""


# Main window

class AikaWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle(APP_NAME)

        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        self.setMinimumSize(800, 500)

        self.agent_process = QProcess(self)

        self.agent_process.setWorkingDirectory(str(PROJECT_ROOT))

        self.agent_process.readyReadStandardOutput.connect(
            self.read_agent_output
        )

        self.agent_process.readyReadStandardError.connect(
            self.read_agent_errors
        )

        self.agent_process.started.connect(
            self.agent_started
        )

        self.agent_process.finished.connect(
            self.agent_finished
        )

        self.agent_process.errorOccurred.connect(
            self.agent_error
        )

        self.shutting_down = False

        # Timer used when stopping the agent
        self.stop_timer = QTimer(self)

        self.stop_timer.setSingleShot(True)

        self.stop_timer.timeout.connect(
            self.force_stop_agent
        )

        # Start the local chat server
        self.chat_server, self.chat_url = start_chat_server()

        self.build_ui()

        self.update_status("Stopped", SECONDARY_TEXT)


    # Build interface

    def build_ui(self):

        central_widget = QWidget()

        self.setCentralWidget(central_widget)

        root_layout = QHBoxLayout(central_widget)

        root_layout.setContentsMargins(12, 12, 12, 12)

        root_layout.setSpacing(12)


        # Sidebar

        sidebar = QFrame()

        sidebar.setObjectName("sidebar")

        sidebar.setFixedWidth(SIDEBAR_WIDTH)

        sidebar_layout = QVBoxLayout(sidebar)

        sidebar_layout.setContentsMargins(18, 22, 18, 18)

        sidebar_layout.setSpacing(12)


        logo = QLabel("AIKA+")

        logo.setObjectName("logo")

        sidebar_layout.addWidget(logo)


        subtitle = QLabel("AI Kitchen Assistant")

        subtitle.setObjectName("subtitle")

        sidebar_layout.addWidget(subtitle)


        sidebar_layout.addSpacing(25)


        self.start_button = QPushButton("Start Agent")

        self.start_button.setObjectName("start_button")

        self.start_button.clicked.connect(
            self.start_agent
        )

        sidebar_layout.addWidget(self.start_button)


        self.stop_button = QPushButton("Stop Agent")

        self.stop_button.clicked.connect(
            self.stop_agent
        )

        sidebar_layout.addWidget(self.stop_button)


        sidebar_layout.addSpacing(15)


        status_heading = QLabel("AGENT STATUS")

        status_heading.setObjectName("section_label")

        sidebar_layout.addWidget(status_heading)


        status_row = QHBoxLayout()

        self.status_dot = QLabel("●")

        self.status_dot.setStyleSheet(
            f"color: {SECONDARY_TEXT}; font-size: 15px;"
        )

        status_row.addWidget(self.status_dot)


        self.status_label = QLabel("Stopped")

        self.status_label.setObjectName("status_label")

        status_row.addWidget(self.status_label)

        status_row.addStretch()

        sidebar_layout.addLayout(status_row)


        sidebar_layout.addStretch()


        self.explorer_button = QPushButton("Show in Explorer")

        self.explorer_button.clicked.connect(
            self.show_in_explorer
        )

        sidebar_layout.addWidget(self.explorer_button)


        # Main panel

        main_panel = QFrame()

        main_panel.setObjectName("main_panel")

        main_layout = QVBoxLayout(main_panel)

        main_layout.setContentsMargins(22, 20, 22, 18)

        main_layout.setSpacing(12)


        heading = QLabel("Conversation")

        heading.setStyleSheet(
            "font-size: 20px; font-weight: bold;"
        )

        main_layout.addWidget(heading)


        conversation_subtitle = QLabel(
            "Your AIKA+ voice assistant session"
        )

        conversation_subtitle.setObjectName("subtitle")

        main_layout.addWidget(conversation_subtitle)


        # Embedded chat interface

        self.chat_view = QWebEngineView()

        self.chat_view.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )

        # Handle microphone permission requests
        self.chat_view.page().permissionRequested.connect(
            self.handle_permission_request
        )

        self.chat_view.setUrl(
            QUrl(self.chat_url)
        )

        main_layout.addWidget(self.chat_view, 1)


        # Agent output heading and toggle button

        log_heading_row = QHBoxLayout()

        log_heading = QLabel("AGENT OUTPUT")

        log_heading.setObjectName("section_label")

        log_heading_row.addWidget(log_heading)

        log_heading_row.addStretch()

        self.log_toggle_button = QPushButton("▼")

        self.log_toggle_button.setObjectName(
            "output_toggle_button"
        )

        self.log_toggle_button.setFixedSize(28, 24)

        self.log_toggle_button.setToolTip(
            "Show agent output"
        )

        self.log_toggle_button.clicked.connect(
            self.toggle_agent_output
        )

        log_heading_row.addWidget(
            self.log_toggle_button
        )

        main_layout.addLayout(log_heading_row)


        # Agent output text area

        self.log_output = QPlainTextEdit()

        self.log_output.setObjectName("log_output")

        self.log_output.setReadOnly(True)

        self.log_output.setLineWrapMode(
            QPlainTextEdit.WidgetWidth
        )

        self.log_output.setMinimumHeight(90)

        self.log_output.setMaximumHeight(130)

        self.log_output.setPlainText(
            "Agent output will appear here."
        )

        # Hidden by default
        self.log_output.hide()

        main_layout.addWidget(self.log_output)


        # Main layout

        root_layout.addWidget(sidebar)

        root_layout.addWidget(main_panel, 1)


    # Toggle agent output

    def toggle_agent_output(self):

        is_visible = self.log_output.isVisible()

        self.log_output.setVisible(not is_visible)

        if is_visible:

            self.log_toggle_button.setText("▼")

            self.log_toggle_button.setToolTip(
                "Show agent output"
            )

        else:

            self.log_toggle_button.setText("▲")

            self.log_toggle_button.setToolTip(
                "Hide agent output"
            )


    # Microphone permissions

    def handle_permission_request(self, permission):

        if (
            permission.permissionType()
            == QWebEnginePermission.PermissionType.MediaAudioCapture
        ):

            answer = QMessageBox.question(
                self,
                "Microphone permission",
                "Allow AIKA+ to access your computer microphone?",
                QMessageBox.Yes | QMessageBox.No
            )

            if answer == QMessageBox.Yes:
                permission.grant()
            else:
                permission.deny()

        else:
            permission.deny()


    # Start agent

    def start_agent(self):

        if self.agent_process.state() != QProcess.NotRunning:
            return

        if not AGENT_FILE.exists():

            self.set_log("Error: main.py could not be found.")

            self.update_status("Error", ERROR_COLOUR)

            return

        self.stop_timer.stop()

        self.set_log("Starting AIKA+ agent...")

        self.update_status("Starting", ACCENT)

        self.start_button.setEnabled(False)

        process_environment = QProcessEnvironment.systemEnvironment()

        process_environment.insert(
            "PYTHONUNBUFFERED",
            "1"
        )

        self.agent_process.setProcessEnvironment(
            process_environment
        )

        self.agent_process.setProgram(sys.executable)

        self.agent_process.setArguments([
            "-u",
            str(AGENT_FILE),
            "dev"
        ])

        self.agent_process.start()


    def agent_started(self):

        self.update_status("Running", ACCENT)

        self.start_button.setEnabled(False)

        self.set_log(
            "AIKA+ agent process started.\n"
            "Waiting for LiveKit registration."
        )


    # Stop agent

    def stop_agent(self):

        self.stop_timer.stop()

        # Disconnect the desktop conversation first
        self.chat_view.page().runJavaScript(
            "disconnectAika();"
        )

        if self.agent_process.state() == QProcess.NotRunning:

            self.update_status("Stopped", SECONDARY_TEXT)

            self.start_button.setEnabled(True)

            return

        self.update_status("Stopping", SECONDARY_TEXT)

        self.start_button.setEnabled(False)

        self.set_log("Stopping AIKA+ agent...")

        self.agent_process.terminate()

        # Force termination if it does not stop normally
        self.stop_timer.start(3000)


    def force_stop_agent(self):

        if self.agent_process.state() != QProcess.NotRunning:

            self.agent_process.kill()


    def agent_finished(self, exit_code, exit_status):

        self.stop_timer.stop()

        self.start_button.setEnabled(True)

        if self.shutting_down:
            return

        if exit_status == QProcess.CrashExit:

            self.update_status("Error", ERROR_COLOUR)

            self.set_log("Agent stopped unexpectedly.")

        elif exit_code == 0:

            self.update_status("Stopped", SECONDARY_TEXT)

            self.set_log("AIKA+ agent stopped.")

        else:

            self.update_status("Error", ERROR_COLOUR)

            self.set_log(
                f"Agent exited with code {exit_code}."
            )


    def agent_error(self, error):

        if error == QProcess.FailedToStart:

            self.update_status("Error", ERROR_COLOUR)

            self.start_button.setEnabled(True)

            self.set_log(
                "Could not start AIKA+.\n"
                "Check your Python environment and project files."
            )


    # Agent output

    def read_agent_output(self):

        output = bytes(
            self.agent_process.readAllStandardOutput()
        ).decode("utf-8", errors="replace").strip()

        if output:
            self.set_log(output)


    def read_agent_errors(self):

        output = bytes(
            self.agent_process.readAllStandardError()
        ).decode("utf-8", errors="replace").strip()

        if output:
            self.set_log(output)


    def set_log(self, message):

        current_text = self.log_output.toPlainText()

        if (
            current_text
            and current_text != "Agent output will appear here."
        ):

            message = current_text + "\n" + message

        # Keep the output from becoming too large
        self.log_output.setPlainText(message[-1200:])

        # Automatically scroll to the latest output
        self.log_output.moveCursor(QTextCursor.End)


    # Status

    def update_status(self, status, colour):

        self.status_label.setText(status)

        self.status_dot.setStyleSheet(
            f"color: {colour}; font-size: 15px;"
        )

        self.stop_button.setEnabled(
            status not in ["Stopped", "Error"]
        )


    # Open project folder

    def show_in_explorer(self):

        if platform.system() == "Windows":

            os.startfile(PROJECT_ROOT)

        elif platform.system() == "Linux":

            subprocess.Popen([
                "xdg-open",
                str(PROJECT_ROOT)
            ])

        elif platform.system() == "Darwin":

            subprocess.Popen([
                "open",
                str(PROJECT_ROOT)
            ])


    # Close application

    def closeEvent(self, event: QCloseEvent):

        self.shutting_down = True

        self.stop_timer.stop()

        # Disconnect LiveKit
        self.chat_view.page().runJavaScript(
            "disconnectAika();"
        )

        # Stop the agent process
        if self.agent_process.state() != QProcess.NotRunning:

            self.agent_process.terminate()

            if not self.agent_process.waitForFinished(3000):

                self.agent_process.kill()

                self.agent_process.waitForFinished(2000)

        # Stop the local chat server
        self.chat_server.shutdown()

        self.chat_server.server_close()

        event.accept()


# Application entry point

def main():

    app = QApplication(sys.argv)

    app.setStyle("Fusion")

    app.setStyleSheet(STYLESHEET)

    window = AikaWindow()

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":

    main()
