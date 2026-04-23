"""Modal dialog that collects NSGA-II budget knobs for a night run.

Design reference: 2026-04-22-bulbopt-night-optimization-design.md §11.1.

The dialog replaces the hardcoded defaults on the "Night Run" button with
engineer-editable inputs (population, generations, runtime budget hours,
high-fidelity budget, seed). It is intentionally lightweight — a
QFormLayout inside a QDialog — so it works with the existing offscreen
Qt test platform.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


DEFAULTS = {
    "budget_hours": 8.0,
    "population": 50,
    "generations": 20,
    "high_fidelity_budget": 10,
    "seed": None,
}


class NightRunDialog(QDialog):
    """Dialog returning a dict of night-run knobs on accept()."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Night Run (NSGA-II)")
        self.setObjectName("night_run_dialog")

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Configure the NSGA-II budget. Leave seed empty for a\n"
                "non-deterministic run.",
                self,
            )
        )

        form = QFormLayout()

        self._budget_hours_input = QDoubleSpinBox(self)
        self._budget_hours_input.setObjectName("night_budget_hours_input")
        self._budget_hours_input.setRange(0.1, 48.0)
        self._budget_hours_input.setDecimals(2)
        self._budget_hours_input.setValue(float(DEFAULTS["budget_hours"]))

        self._population_input = QSpinBox(self)
        self._population_input.setObjectName("night_population_input")
        self._population_input.setRange(2, 1000)
        self._population_input.setValue(int(DEFAULTS["population"]))

        self._generations_input = QSpinBox(self)
        self._generations_input.setObjectName("night_generations_input")
        self._generations_input.setRange(1, 500)
        self._generations_input.setValue(int(DEFAULTS["generations"]))

        self._high_fidelity_input = QSpinBox(self)
        self._high_fidelity_input.setObjectName("night_high_fidelity_input")
        self._high_fidelity_input.setRange(0, 200)
        self._high_fidelity_input.setValue(int(DEFAULTS["high_fidelity_budget"]))

        self._seed_input = QLineEdit("", self)
        self._seed_input.setObjectName("night_seed_input")
        self._seed_input.setPlaceholderText("leave blank for random")

        form.addRow("Runtime budget (hours)", self._budget_hours_input)
        form.addRow("Population", self._population_input)
        form.addRow("Generations", self._generations_input)
        form.addRow("High-fidelity budget", self._high_fidelity_input)
        form.addRow("Random seed", self._seed_input)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            parent=self,
        )
        buttons.setObjectName("night_run_dialog_buttons")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict:
        raw_seed = self._seed_input.text().strip()
        seed: int | None
        try:
            seed = int(raw_seed) if raw_seed else None
        except ValueError:
            seed = None
        return {
            "budget_hours": float(self._budget_hours_input.value()),
            "population": int(self._population_input.value()),
            "generations": int(self._generations_input.value()),
            "high_fidelity_budget": int(self._high_fidelity_input.value()),
            "seed": seed,
        }
