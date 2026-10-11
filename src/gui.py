
import os
import sys
from pathlib import Path
import PySide6

from PySide6.QtCore import QProcess, QProcessEnvironment, QTimer, Qt
from PySide6.QtGui import QCloseEvent, QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


# --------------------------------------------------
# Customisation settings
# Change these values to customise the appearance.
# --------------------------------------------------

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

# Find the project root from this file's location.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENT_FILE = PROJECT_ROOT / "src" / "main.py"


STYLESHEET = f"""
QMainWindow {{
    background-color: {BACKGROUND};
}}

QWidget {{
    color: {TEXT};
    font-family: "Segoe UI";
    font-size: 10pt;
}}

QFrame#sidebar {{
    background-color: {SIDEBAR_BACKGROUND};
    border-radius: 12px;
}}

QFrame#main_panel {{
    background-color: {PANEL_BACKGROUND};
    border-radius: 12px;
}}

QLabel#subtitle {{
    color: {SECONDARY_TEXT};
    font-size: 9pt;
}}

QLabel#section_label {{
    color: {SECONDARY_TEXT};
    font-size: 9pt;
    font-weight: bold;
}}

QLabel#status {{
    font-weight: bold;
}}

QPushButton {{
    background-color: #292E36;
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 11px;
    text-align: center;
}}

QPushButton:hover {{
    background-color: #343B45;
}}

QPushButton:disabled {{
    color: #69717D;
    background-color: #252930;
}}

QPushButton#start_button {{
    background-color: {ACCENT};
    color: #171A1F;
    border: none;
    font-weight: bold;
}}

QPushButton#start_button:hover {{
    background-color: #70D8C8;
}}

QPushButton#start_button:disabled {{
    background-color: #39534F;
    color: #A4B9B5;
}}

QLabel#conversation_placeholder {{
    color: {SECONDARY_TEXT};
    padding: 20px;
}}

QLabel#log_title {{
    color: {SECONDARY_TEXT};
    font-weight: bold;
}}

QLabel#log_output {{
    color: {SECONDARY_TEXT};
    background-color: {BACKGROUND};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 10px;
    font-family: Consolas;
    font-size: 9pt;
}}
"""


class AikaWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(f"{APP_NAME} | AI Kitchen Assistant")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(800, 500)

        # The agent runs separately from the GUI.
        self.agent_process = QProcess(self)
        self.agent_process.setWorkingDirectory(str(PROJECT_ROOT))

        self.agent_process.readyReadStandardOutput.connect(
            self.read_agent_output
        )
        self.agent_process.readyReadStandardError.connect(
            self.read_agent_errors
        )
        self.agent_process.started.connect(self.agent_started)
        self.agent_process.finished.connect(self.agent_finished)
        self.agent_process.errorOccurred.connect(self.agent_error)

        self.shutting_down = False
        self.stop_timer = QTimer(self)
        self.stop_timer.setSingleShot(True)
        self.stop_timer.timeout.connect(self.force_stop_agent)

        self.build_ui()
        self.update_status("Stopped", SECONDARY_TEXT)

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(16)

        # ---------------- Left sidebar ----------------

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(SIDEBAR_WIDTH)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 20, 16, 16)
        sidebar_layout.setSpacing(12)

        logo = QLabel("AIKA+")
        logo.setFont(QFont("Segoe UI", 21, QFont.Weight.Bold))

        subtitle = QLabel("AI Kitchen Assistant")
        subtitle.setObjectName("subtitle")

        sidebar_layout.addWidget(logo)
        sidebar_layout.addWidget(subtitle)
        sidebar_layout.addSpacing(22)

        controls_label = QLabel("CONTROLS")
        controls_label.setObjectName("section_label")
        sidebar_layout.addWidget(controls_label)

        self.start_button = QPushButton("▶   Start Agent")
        self.start_button.setObjectName("start_button")
        self.start_button.clicked.connect(self.start_agent)

        self.stop_button = QPushButton("■   Stop Agent")
        self.stop_button.clicked.connect(self.stop_agent)

        sidebar_layout.addWidget(self.start_button)
        sidebar_layout.addWidget(self.stop_button)

        sidebar_layout.addSpacing(18)

        status_heading = QLabel("AGENT STATUS")
        status_heading.setObjectName("section_label")
        sidebar_layout.addWidget(status_heading)

        status_row = QHBoxLayout()
        self.status_dot = QLabel("●")
        self.status_dot.setFixedWidth(16)

        self.status_label = QLabel("Stopped")
        self.status_label.setObjectName("status")

        status_row.addWidget(self.status_dot)
        status_row.addWidget(self.status_label)
        status_row.addStretch()

        sidebar_layout.addLayout(status_row)

        sidebar_layout.addStretch()

        self.explorer_button = QPushButton("📁   Show in Explorer")
        self.explorer_button.clicked.connect(self.show_in_explorer)
        sidebar_layout.addWidget(self.explorer_button)

        # ---------------- Main content ----------------

        main_panel = QFrame()
        main_panel.setObjectName("main_panel")

        main_layout = QVBoxLayout(main_panel)
        main_layout.setContentsMargins(24, 22, 24, 20)
        main_layout.setSpacing(14)

        heading = QLabel("Conversation")
        heading.setFont(QFont("Segoe UI", 17, QFont.Weight.DemiBold))

        conversation_subtitle = QLabel(
            "Your AIKA+ voice assistant session"
        )
        conversation_subtitle.setObjectName("subtitle")

        main_layout.addWidget(heading)
        main_layout.addWidget(conversation_subtitle)

        self.conversation_placeholder = QLabel(
            "Welcome to AIKA+\\n\\n"
            "Start the agent to launch the voice assistant.\\n"
            "Conversation messages will be connected in a later stage."
        )
        self.conversation_placeholder.setObjectName(
            "conversation_placeholder"
        )
        self.conversation_placeholder.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.conversation_placeholder.setWordWrap(True)
        self.conversation_placeholder.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        main_layout.addWidget(self.conversation_placeholder, 1)

        log_heading = QLabel("AGENT OUTPUT")
        log_heading.setObjectName("log_title")
        main_layout.addWidget(log_heading)

        self.log_output = QLabel("Agent output will appear here.")
        self.log_output.setObjectName("log_output")
        self.log_output.setWordWrap(True)
        self.log_output.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self.log_output.setMinimumHeight(75)
        self.log_output.setMaximumHeight(110)

        main_layout.addWidget(self.log_output)

        root_layout.addWidget(sidebar)
        root_layout.addWidget(main_panel, 1)

    # ---------------- Agent controls ----------------

    def start_agent(self):
        if self.agent_process.state() != QProcess.ProcessState.NotRunning:
            return

        if not AGENT_FILE.exists():
            self.update_status("Error", ERROR_COLOUR)
            self.set_log(f"Agent file not found: {AGENT_FILE}")
            return

        self.stop_timer.stop()
        self.set_log("Starting AIKA+ agent...")
        self.update_status("Starting", "#E8B86D")
        self.start_button.setEnabled(False)

        # Use the same Python interpreter running this GUI.
        # When launched through .venv, this is the venv interpreter.
        self.agent_process.setProgram(sys.executable)
        self.agent_process.setArguments([
            "-u",
            str(AGENT_FILE),
            "dev",
        ])

        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONUNBUFFERED", "1")
        self.agent_process.setProcessEnvironment(environment)

        self.agent_process.start()

    def agent_started(self):
        self.update_status("Running", ACCENT)
        self.start_button.setEnabled(False)
        self.set_log(
            "Agent process started. Waiting for LiveKit registration..."
        )

    def stop_agent(self):
        self.stop_timer.stop()

        if self.agent_process.state() == QProcess.ProcessState.NotRunning:
            self.update_status("Stopped", SECONDARY_TEXT)
            self.start_button.setEnabled(True)
            return

        self.update_status("Stopping", "#E8B86D")
        self.start_button.setEnabled(False)
        self.set_log("Stopping agent process...")

        # Try a normal termination first.
        self.agent_process.terminate()

        # Force termination if it does not stop promptly.
        self.stop_timer.start(3000)

    def force_stop_agent(self):
        if self.agent_process.state() != QProcess.ProcessState.NotRunning:
            self.agent_process.kill()

    def agent_finished(self, exit_code, exit_status):
        self.stop_timer.stop()
        self.start_button.setEnabled(True)

        if self.shutting_down:
            return

        if exit_status == QProcess.ExitStatus.CrashExit:
            self.update_status("Error", ERROR_COLOUR)
            self.set_log("Agent process crashed.")
        elif exit_code == 0:
            self.update_status("Stopped", SECONDARY_TEXT)
            self.set_log("Agent process stopped.")
        else:
            self.update_status("Error", ERROR_COLOUR)
            self.set_log(
                f"Agent exited with error code {exit_code}."
            )

    def agent_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.update_status("Error", ERROR_COLOUR)
            self.start_button.setEnabled(True)
            self.set_log(
                "Could not start Python. Check the virtual environment "
                "and project path."
            )

    # ---------------- Output and status ----------------

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
        # Keep the output panel readable.
        self.log_output.setText(message[-1200:])

    def update_status(self, status, colour):
        self.status_label.setText(status)
        self.status_dot.setStyleSheet(f"color: {colour};")

        if status == "Running":
            self.stop_button.setEnabled(True)
        elif status in ("Stopped", "Error"):
            self.stop_button.setEnabled(False)
        else:
            self.stop_button.setEnabled(True)

    # ---------------- Utilities ----------------

    def show_in_explorer(self):
        # Open the project root without displaying .env contents.
        os.startfile(str(PROJECT_ROOT))

    def closeEvent(self, event: QCloseEvent):
        self.shutting_down = True
        self.stop_timer.stop()

        if self.agent_process.state() != QProcess.ProcessState.NotRunning:
            self.agent_process.terminate()

            if not self.agent_process.waitForFinished(3000):
                self.agent_process.kill()
                self.agent_process.waitForFinished(2000)

        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)

    window = AikaWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
