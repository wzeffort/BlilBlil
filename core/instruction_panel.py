import os
import sys
import tkinter as tk
from tkinter import ttk

from core.utils import image_subsample_factor


def resource_path(*parts: str) -> str:
    project_root = getattr(
        sys,
        "_MEIPASS",
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    return os.path.join(project_root, *parts)


class InstructionPanel(ttk.LabelFrame):
    def __init__(
        self,
        parent,
        steps: list[str],
        image_name: str,
        max_image_width: int = 520,
    ):
        super().__init__(parent, text="使用说明", padding=10)

        for index, step in enumerate(steps, start=1):
            ttk.Label(
                self,
                text=f"{index}. {step}",
                foreground="#495057",
                wraplength=760,
                justify="left",
            ).pack(anchor="w", pady=(0, 4))

        image_path = resource_path("images", image_name)
        try:
            image = tk.PhotoImage(file=image_path)
            factor = image_subsample_factor(image.width(), max_image_width)
            if factor > 1:
                image = image.subsample(factor, factor)
            self.instruction_image = image
            ttk.Label(self, image=image).pack(anchor="center", pady=(8, 0))
        except (tk.TclError, OSError):
            ttk.Label(
                self,
                text=f"说明图片暂时无法加载：{image_name}",
                foreground="#b02a37",
            ).pack(anchor="w", pady=(8, 0))
