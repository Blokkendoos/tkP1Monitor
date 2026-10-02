#!/usr/bin/env python3

"""
Slimme Meter monitor.

Shows the current consumed energy (W) values from a HomeWizard P1 Monitor.

Requirements:
    pip install python-homewizard-energy matplotlib numpy

HomeWizard:
    - Local API acitvated
    - IP-adres adjust below

TODO
----
* Polynomial interpolation

2026-10-01 New
"""

import asyncio
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk

from homewizard_energy import HomeWizardEnergyV1

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg,
    NavigationToolbar2Tk,
)

import numpy as np


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

IP_ADDRESS = '192.168.178.221'

# HomeWizard query freqency
QUERY_FREQUENCY = 1  # Hz
MEASUREMENT_INTERVAL = 1 / QUERY_FREQUENCY

# Maximum number of points kept in the graph
MAX_POINTS = 300


class MonitorWindow(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title('HomeWizard P1 Monitor Measurements')
        self.geometry('1000x650')

        # -------------------------------------------------
        # State
        # -------------------------------------------------

        self.running = True
        self.plotting = False

        # Queue shared between asyncio thread and Tkinter
        self.measurement_queue = queue.Queue()

        # Thread running the asyncio event loop
        self.api_thread = None
        self.api_loop = None

        # Data for graph
        self.units = 'W'
        self.x_time = []
        self.y_consumed = []
        self.y_supplied = []
        self.color_consumed = 'red'
        self.color_supplied = 'green'

        self.start_time = None

        # -------------------------------------------------
        # Window close handler
        # -------------------------------------------------

        self.protocol('WM_DELETE_WINDOW', self.stop)

        # -------------------------------------------------
        # Left control frame
        # -------------------------------------------------

        left_frame = ttk.Frame(self)
        left_frame.pack(side='left', padx=10, pady=10, fill='y')
        left_frame_label = \
            ttk.Label(left_frame, text='HomeWizard P1', font=('TkDefaultFont', 12, 'bold'))
        left_frame_label.pack(side='top', padx=10, pady=(5, 20))

        # Start button
        self.start_button = ttk.Button(left_frame, text='Start',
                                       command=self.start_plot)
        self.start_button.pack(side='top', padx=10, pady=5, fill='x')

        # Pause button
        self.pause_button = ttk.Button(left_frame, text='Pause',
                                       command=self.pause_plot)
        self.pause_button.pack(side='top', padx=10, pady=5, fill='x')

        # Resume button
        self.resume_button = ttk.Button(left_frame, text='Resume',
                                        command=self.resume_plot)
        self.resume_button.pack(side='top', padx=10, pady=5, fill='x')

        # Separator
        sep = ttk.Separator(left_frame, orient='horizontal')
        sep.pack(fill='x', padx=5, pady=20)

        # Current value
        energy_label = ttk.Label(left_frame, text='Energy import:')
        energy_label.pack(side='top', padx=10, pady=(5, 2))
        self.energy_value = tk.StringVar(value='-- W')
        energy_frame = ttk.Label(left_frame, textvariable=self.energy_value, font=('TkDefaultFont', 14, 'bold'))
        energy_frame.pack(side='top', padx=10, pady=(0, 15))

        # Status
        status_label = ttk.Label(left_frame, text='Status:')
        status_label.pack(side='top', padx=10, pady=(5, 2))
        self.status = tk.StringVar(value='Starting...')
        status_frame = ttk.Label(left_frame, textvariable=self.status, wraplength=150)
        status_frame.pack(side='top', padx=10, pady=5)

        # -------------------------------------------------
        # Matplotlib figure
        # -------------------------------------------------

        self.fig = plt.Figure(figsize=(7, 5), dpi=100)
        self.ax = self.fig.add_subplot(1, 1, 1)
        self.line_y1, = self.ax.plot([], [], linewidth=2, color=self.color_consumed)
        self.line_y2, = self.ax.plot([], [], linewidth=2, color=self.color_supplied)
        self.ax.set_xlabel('Time (seconds)', fontsize=11)
        self.ax.set_ylabel(f'Consumption ({self.units})', fontsize=11)
        self.ax.set_title('HomeWizard P1 Monitor')
        self.ax.grid(True)
        self.fig.tight_layout()

        # Embed Matplotlib in Tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(side='top', fill='both', expand=True)

        # Matplotlib toolbar
        self.toolbar = NavigationToolbar2Tk(self.canvas, self)
        self.toolbar.update()

        # -------------------------------------------------
        # Start API thread
        # -------------------------------------------------

        self.api_thread = threading.Thread(target=self.run_asyncio, daemon=True)
        self.api_thread.start()

        # -------------------------------------------------
        # Start Tkinter queue polling
        # -------------------------------------------------

        self.after(100, self.process_measurements)

    # =====================================================
    # Asyncio / HomeWizard
    # =====================================================

    def run_asyncio(self):
        """Run the asyncio event loop in a background thread."""
        self.api_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.api_loop)
        try:
            self.api_loop.run_until_complete(self.monitor_homewizard())
        except Exception as e:
            self.measurement_queue.put(('error', str(e)))
        finally:
            self.api_loop.close()

    async def monitor_homewizard(self):
        """Continuously read measurements from HomeWizard."""
        try:
            async with HomeWizardEnergyV1(host=IP_ADDRESS) as api:
                # Get device information once
                try:
                    device = await api.device()
                    self.measurement_queue.put(('status',
                                                f'Connected: {device.product_name}'))
                except Exception:
                    self.measurement_queue.put(('status',
                                                'Connected to HomeWizard'))
                # Continuously read measurements
                while self.running:
                    try:
                        measurement = await api.measurement()
                        # The current net energy (W)
                        # Positive value = consuming
                        value = measurement.power_w
                        self.measurement_queue.put(('measurement', value))
                    except Exception as e:
                        self.measurement_queue.put(('error', str(e)))
                    await asyncio.sleep(
                        MEASUREMENT_INTERVAL
                    )
        except Exception as e:
            self.measurement_queue.put(('error', str(e)))

    # =====================================================
    # Tkinter queue
    # =====================================================

    def process_measurements(self):
        """
        Read measurements from the thread-safe queue.

        IMPORTANT:
        All Tkinter and Matplotlib operations happen here,
        in the main Tkinter thread.
        """
        try:
            while True:
                message_type, value = (self.measurement_queue.get_nowait())
                if message_type == 'measurement':
                    self.handle_measurement(value)
                elif message_type == 'status':
                    self.status.set(value)
                elif message_type == 'error':
                    self.status.set(f'API error: {value}')
        except queue.Empty:
            pass

        # Schedule next check
        if self.running:
            self.after(100, self.process_measurements)

    # =====================================================
    # Measurement handling
    # =====================================================

    def handle_measurement(self, value):
        """
        Handle one HomeWizard measurement.

        This function runs in the Tkinter thread.
        """
        if value is None:
            return
        try:
            value = float(value)
        except (TypeError, ValueError):
            return
        # Show current value
        self.energy_value.set(f'{value:.3f} {self.units}')
        self.status.set('Connected')
        # Only add values while plotting
        if not self.plotting:
            return
        # Start timer on first measurement
        if self.start_time is None:
            self.start_time = time.monotonic()
        elapsed = (time.monotonic() - self.start_time)
        self.x_time.append(elapsed)
        if value < 0.0:
            self.y_consumed.append(np.nan)
            self.y_supplied.append(value)
        else:
            self.y_consumed.append(value)
            self.y_supplied.append(np.nan)
        # Keep only the last MAX_POINTS
        if len(self.x_time) > MAX_POINTS:
            self.x_time = self.x_time[-MAX_POINTS:]
            self.y_consumed = self.y_consumed[-MAX_POINTS:]
            self.y_supplied = self.y_supplied[-MAX_POINTS:]
        # Update graph
        self.line_y1.set_data(self.x_time, self.y_consumed)
        self.line_y2.set_data(self.x_time, self.y_supplied)
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw_idle()

    # =====================================================
    # Button callbacks
    # =====================================================

    def start_plot(self):
        """Clear the graph and start recording."""
        self.x_time.clear()
        self.y_consumed.clear()
        self.y_supplied.clear()

        self.start_time = time.monotonic()
        self.plotting = True
        self.line_y1.set_data([], [])
        self.line_y2.set_data([], [])
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw_idle()
        self.status.set('Plotting...')

    def pause_plot(self):
        """
        Pause graph recording.

        HomeWizard polling continues.
        """
        self.plotting = False
        self.status.set('Plot paused')

    def resume_plot(self):
        """Resume graph recording."""
        if not self.plotting:
            # Continue using the existing graph time
            if self.x_time:
                last_x = self.x_time[-1]
                self.start_time = (time.monotonic() - last_x)
            else:
                self.start_time = time.monotonic()
        self.plotting = True
        self.status.set('Plotting...')

    # =====================================================
    # Shutdown
    # =====================================================

    def stop(self):
        """Stop the application cleanly."""
        self.running = False
        self.plotting = False
        self.status.set('Stopping...')
        # Give the asyncio task a chance to exit.
        if self.api_loop is not None:
            try:
                self.api_loop.call_soon_threadsafe(lambda: None)
            except RuntimeError:
                pass
        self.destroy()


if __name__ == '__main__':
    app = MonitorWindow()
    app.mainloop()
