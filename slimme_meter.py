"""
Plot actuele waarden van de slimme meter.

Dit is slechts het tk scherm, met dummy-waarden

TODO
De P1 Monitor waarden tonen


2026-10-01 New
"""

import tkinter as tk
from tkinter import ttk

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg \
    import FigureCanvasTkAgg, NavigationToolbar2Tk

import numpy as np


class MonitorWindow(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title('I-V live plot')
        self.geometry('800x500')

        # Data
        self.x_data = []
        self.y_data = []

        # ---------------------------------------------------------
        # Left control frame
        # ---------------------------------------------------------
        left_frame = ttk.Frame(self)
        left_frame.pack(side='left', padx=10, pady=10, fill='y')

        # Voltage range
        voltage_range_label = ttk.Label(left_frame, text='Voltage range')
        voltage_range_label.pack(side='top', padx=10, pady=2)
        self.voltage_range = tk.DoubleVar(value=10)
        voltage_range_spinbox = \
            ttk.Spinbox(left_frame, from_=-300, to=500, increment=1,
                        textvariable=self.voltage_range, width=8)
        voltage_range_spinbox.pack(side='top', padx=10, pady=5)

        # Voltage step
        voltage_step_label = ttk.Label(left_frame, text='Step')
        voltage_step_label.pack(side='top', padx=10, pady=2)
        self.step = tk.DoubleVar(value=1)
        step_spinbox = \
            ttk.Spinbox(left_frame, from_=0.1, to=500, increment=0.1,
                        textvariable=self.step, width=9)
        step_spinbox.pack(side='top', padx=10, pady=5)

        # Start button
        self.start = tk.BooleanVar(value=False)

        start_button = \
            ttk.Button(left_frame, text='Start', command=self.start_plot)
        start_button.pack(side='top', padx=10, pady=10)

        # Resume button
        resume_button = \
            ttk.Button(left_frame, text='Resume', command=self.resume_plot)
        resume_button.pack(side='top', padx=10, pady=10)

        # Pause button
        pause_button = \
            ttk.Button(left_frame, text='Pause', command=self.pause_plot)
        pause_button.pack(side='top', padx=10, pady=10)

        # ---------------------------------------------------------
        # Matplotlib figure
        # ---------------------------------------------------------
        self.fig = plt.Figure(figsize=(5, 4), dpi=100)
        self.ax = self.fig.add_subplot(1, 1, 1)
        self.line, = self.ax.plot([], [], 'b-')
        self.ax.set_xlabel('Voltage / V', fontsize=12)
        self.ax.set_ylabel('Current / A', fontsize=12)
        self.ax.grid(True)
        self.fig.tight_layout()

        # Embed Matplotlib in Tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(side='top', fill='both', expand=True)

        # Matplotlib toolbar
        self.toolbar = NavigationToolbar2Tk(self.canvas, self)
        self.toolbar.update()

        # Current x position
        self.current_x = 0
        # Start periodic update
        self.after(1000, self.update_plot)

    # -------------------------------------------------------------
    # Button callbacks
    # -------------------------------------------------------------

    def start_plot(self):
        """Start a new plot."""
        self.x_data.clear()
        self.y_data.clear()
        self.current_x = 0
        self.start.set(True)
        self.line.set_data(self.x_data, self.y_data)
        self.canvas.draw_idle()

    def pause_plot(self):
        """Pause the plot."""
        self.start.set(False)

    def resume_plot(self):
        """Resume the plot."""
        self.start.set(True)

    # -------------------------------------------------------------
    # Plot update
    # -------------------------------------------------------------

    def update_plot(self):
        """Add one data point every second."""
        if self.start.get():
            try:
                voltage_range = float(self.voltage_range.get())
                step = float(self.step.get())
            except (tk.TclError, ValueError):
                step = 1
                voltage_range = 10

            # Avoid a zero or negative step
            if step <= 0:
                step = 1

            # Add a new point
            if self.current_x <= voltage_range:
                x = self.current_x
                y = np.sin(x / 5)
                self.x_data.append(x)
                self.y_data.append(y)
                # Update line
                self.line.set_data(self.x_data, self.y_data)
                # Rescale axes
                self.ax.relim()
                self.ax.autoscale_view()
                # Redraw
                self.canvas.draw_idle()
                # Move to next voltage
                self.current_x += step
            else:
                # Reached the end
                self.start.set(False)

        # Run again after 1 second
        self.after(1000, self.update_plot)


if __name__ == '__main__':
    app = MonitorWindow()
    app.mainloop()
