#!/usr/bin/env python3

"""
Slimme Meter monitor.

Shows the current consumed energy (W) values from a HomeWizard P1 Monitor.

Requirements:
    pip install python-homewizard-energy matplotlib numpy scipy

HomeWizard:
    - Local API activated
    - IP-address adjust below

2026-10-01 New
2026-10-03 Added cubic spline interpolation
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
from matplotlib.collections import LineCollection

import numpy as np

from scipy.interpolate import CubicSpline

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

IP_ADDRESS = '192.168.178.221'
GAS_METER = "gas_meter_G0090004415178525"

# HomeWizard query frequency
QUERY_FREQUENCY = 1  # Hz
MEASUREMENT_INTERVAL = 1 / QUERY_FREQUENCY

# Maximum number of measured points kept in the graph
MAX_POINTS = 500

# Number of points used to draw the smooth interpolation
INTERPOLATION_POINTS = 1500


class MonitorWindow(tk.Tk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.title('HomeWizard P1 Monitor Measurements')
        self.geometry('1000x650')

        # -------------------------------------------------
        # State
        # -------------------------------------------------

        self.running = True
        self.first_run = True
        self.plotting = False
        self.measurement_queue = queue.Queue()
        self.api_thread = None
        self.api_loop = None

        # Electricity
        self.units = 'W'
        self.x_time = []
        self.y_measured = []
        self.color_consumed = 'red'
        self.color_supplied = 'green'
        self.start_time = None

        # Gas
        self.x2_time = []
        self.y2_measured = []

        # -------------------------------------------------
        # Window close handler
        # -------------------------------------------------

        self.protocol('WM_DELETE_WINDOW', self.stop)

        # -------------------------------------------------
        # Left control frame
        # -------------------------------------------------

        left_frame = ttk.Frame(self)
        left_frame.pack(side='left', padx=10, pady=10, fill='y')

        left_frame_label = ttk.Label(
            left_frame,
            text='HomeWizard P1',
            font=('TkDefaultFont', 12, 'bold'),
        )
        left_frame_label.pack(
            side='top',
            padx=10,
            pady=(5, 20),
        )
        self.pause_button = ttk.Button(
            left_frame,
            text='Pause',
            command=self.pause_plot,
        )
        self.pause_button.pack(
            side='top',
            padx=10,
            pady=5,
            fill='x',
        )
        self.resume_button = ttk.Button(
            left_frame,
            text='Resume',
            command=self.resume_plot,
        )
        self.resume_button.pack(
            side='top',
            padx=10,
            pady=5,
            fill='x',
        )
        separator = ttk.Separator(left_frame, orient='horizontal')
        separator.pack(fill='x', padx=5, pady=20)

        energy_label = ttk.Label(left_frame, text='Energy import:')
        energy_label.pack(
            side='top',
            padx=10,
            pady=(5, 2),
        )
        self.energy_value = tk.StringVar(value='-- W')
        energy_frame = ttk.Label(
            left_frame,
            textvariable=self.energy_value,
            font=('TkDefaultFont', 14, 'bold'),
        )
        energy_frame.pack(
            side='top',
            padx=10,
            pady=(0, 15),
        )
        status_label = ttk.Label(
            left_frame,
            text='Status:',
        )
        status_label.pack(
            side='top',
            padx=10,
            pady=(5, 2),
        )
        self.status = tk.StringVar(value='Starting...')
        status_frame = ttk.Label(
            left_frame,
            textvariable=self.status,
            wraplength=150,
        )
        status_frame.pack(
            side='top',
            padx=10,
            pady=5,
        )

        # -------------------------------------------------
        # Matplotlib figure
        # -------------------------------------------------

        self.fig, axs = plt.subplots(2)
        self.ax = axs[0]
        self.ax2 = axs[1]

        self.data_width = 1
        self.data_style = '--'
        self.data_alpha = 0.65

        self.smooth_width = 2
        self.smooth_style = '-'
        self.smooth_alpha = 1.0

        # Electricity

        # Manual Legend
        self.legend_consumed, = self.ax.plot(
            [],
            [],
            linewidth=self.smooth_width,
            linestyle=self.smooth_style,
            alpha=self.smooth_alpha,
            color=self.color_consumed,
            label='Consumed',
        )
        self.legend_supplied, = self.ax.plot(
            [],
            [],
            linewidth=self.smooth_width,
            linestyle=self.smooth_style,
            alpha=self.smooth_alpha,
            color=self.color_supplied,
            label='Supplied',
        )

        # Lines
        self.lc_measured = None
        self.lc_interp = None
        self.line_interp, = self.ax.plot(
            [],
            [],
            linewidth=self.smooth_width,
            linestyle=self.smooth_style,
            alpha=self.smooth_alpha,
            # label='Measured (cubic)',
        )
        self.line_measured, = self.ax.plot(
            [],
            [],
            linewidth=self.data_width,
            linestyle=self.data_style,
            alpha=self.data_alpha,
            # label='Measured',
        )
        self.ax.set_xlabel('Time (seconds)', fontsize=11)
        self.ax.set_ylabel(
            f'Consumption ({self.units})',
            fontsize=11,
        )
        self.ax.set_title('HomeWizard P1 Monitor')
        self.ax.grid(True)
        self.ax.legend()

        # Gas

        # Lines
        self.lc2_measured = None
        self.lc2_interp = None
        self.gas_measured, = self.ax2.plot(
            [],
            [],
            linewidth=self.data_width,
            linestyle=self.data_style,
            alpha=self.data_alpha,
            # label='Measured',
        )
        self.gas_interp, = self.ax2.plot(
            [],
            [],
            linewidth=self.smooth_width,
            linestyle=self.smooth_style,
            alpha=self.smooth_alpha,
            # label='Measured (cubic)',
        )
        self.ax2.grid(True)
        self.ax2.legend()

        self.fig.tight_layout()
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(
            side='top',
            fill='both',
            expand=True,
        )
        self.toolbar = NavigationToolbar2Tk(self.canvas, self)
        self.toolbar.update()

        # -------------------------------------------------
        # Start API thread
        # -------------------------------------------------

        self.api_thread = threading.Thread(
            target=self.run_asyncio,
            daemon=True,
        )
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
            self.api_loop.run_until_complete(
                self.monitor_homewizard(),
            )
        except Exception as error:
            self.measurement_queue.put(
                ('error', str(error)),
            )
        finally:
            self.api_loop.close()

    async def monitor_homewizard(self):
        """Continuously read measurements from HomeWizard."""
        try:
            async with HomeWizardEnergyV1(host=IP_ADDRESS) as api:
                try:
                    device = await api.device()
                    self.measurement_queue.put(
                        ('status',
                         f'Connected: {device.product_name}')
                    )
                except Exception:
                    self.measurement_queue.put(
                        ('status',
                         'Connected to HomeWizard')
                    )

                while self.running:
                    try:
                        data = await api.measurement()
                        # Current net energy (W).
                        # Positive value = consuming.
                        electricity = data.power_w
                        # Gas consumption
                        gas = data.external_devices[GAS_METER].value
                        gas_unit = data.external_devices[GAS_METER].unit
                        # TODO data object instead of a list
                        self.measurement_queue.put(
                            ('measurement', [electricity, gas, gas_unit]),
                        )
                    except Exception as error:
                        self.measurement_queue.put(
                            ('error', str(error)),
                        )
                    await asyncio.sleep(MEASUREMENT_INTERVAL)
        except Exception as error:
            self.measurement_queue.put(
                ('error', str(error)),
            )

    # =====================================================
    # Tkinter queue
    # =====================================================

    def process_measurements(self):
        """
        Read measurements from the thread-safe queue.

        All Tkinter and Matplotlib operations happen here,
        in the main Tkinter thread.
        """
        try:
            while True:
                message_type, data = (
                    self.measurement_queue.get_nowait()
                )
                if message_type == 'measurement':
                    self.handle_measurement(data)
                elif message_type == 'status':
                    self.status.set(data)
                elif message_type == 'error':
                    self.status.set(f'API error: {data}')
        except queue.Empty:
            pass

        if self.running:
            self.after(100, self.process_measurements)

    # =====================================================
    # Cubic interpolation
    # =====================================================

    def update_electricity_interpolation(self):
        """Calculate and display cubic spline interpolation."""
        # CubicSpline requires at least four valid points
        if len(self.x_time) < 4:
            return

        cs = CubicSpline(
            self.x_time,
            self.y_measured,
            bc_type='natural'
        )
        x_smooth = np.linspace(
            self.x_time[0],
            self.x_time[-1],
            INTERPOLATION_POINTS
        )
        y_smooth = cs(x_smooth)

        # Define the condition for colors
        colors = [
            self.color_supplied
            if val < 0 else self.color_consumed for val in y_smooth]

        # Create a set of line segments so that we can color them individually
        points = np.array([x_smooth, y_smooth]).T.reshape(-1, 1, 2)
        segments = np.concatenate([points[:-1], points[1:]], axis=1)

        self.line_interp.set_data(
            x_smooth,
            y_smooth
        )

        # Create the LineCollection object
        if self.lc_interp is not None:
            self.lc_interp.remove()
        self.lc_interp = LineCollection(segments,
                                        colors=colors,
                                        linewidth=self.smooth_width,
                                        linestyle=self.smooth_style)
        self.ax.add_collection(self.lc_interp)

    # =====================================================
    # Measurement handling
    # =====================================================

    def handle_measurement(self, data):
        """
        Handle one HomeWizard measurement.

        This function runs in the Tkinter thread.
        """
        if data is None:
            return
        try:
            # TODO data object instead of list
            value = float(data[0])
            gas = float(data[1])
            gas_unit = data[2]
        except (TypeError, ValueError):
            print("Invalid data received...")
            return

        self.energy_value.set(f'{value:.3f} {self.units}')
        self.status.set('Connected')

        if self.first_run:
            self.first_run = False
            self.start_plot()
            return

        if not self.plotting:
            return

        self.update_measurement(self.ax,
                                self.x_time,
                                self.y_measured,
                                self.line_measured,
                                value,
                                self.units,
                                self.lc_measured)
        self.update_electricity_interpolation()

        self.update_measurement(self.ax2,
                                self.x2_time,
                                self.y2_measured,
                                self.gas_measured,
                                gas,
                                gas_unit,
                                self.lc2_measured)
        # self.update_gas_interpolation()
        self.ax.relim()
        self.ax.autoscale_view()
        self.ax2.relim()
        self.ax2.autoscale_view()
        self.canvas.draw_idle()

    def update_measurement(self,
                           ax,
                           x_time,
                           y_measured,
                           line_measured,
                           value,
                           unit,
                           lc=None):
        """
        @brief Update the plot with latest value.

        @param ax : The matplotlib axis
        @param x_time : the x dimension value
        @param y_measured : the y-dimension value
        @param line_measured : the plotted line values
        @param lc : the line collection
        @param value : the current measurement
        @param unit : unit
        """
        if self.start_time is None:
            self.start_time = time.monotonic()

        elapsed = time.monotonic() - self.start_time
        x_time.append(elapsed)
        y_measured.append(value)

        if len(x_time) > MAX_POINTS:
            x_time = x_time[-MAX_POINTS:]
            y_measured = y_measured[-MAX_POINTS:]

        line_measured.set_data(
            x_time,
            y_measured
        )

        # https://blog.finxter.com/5-best-ways-to-plot-a-multicolored-line-based-on-a-condition-in-python-matplotlib/
        # Define the condition for colors
        colors = [
            self.color_supplied
            if val < 0 else self.color_consumed for val in y_measured]

        # Create a set of line segments so that we can color them individually
        points = np.array([self.x_time, y_measured]).T.reshape(-1, 1, 2)
        segments = np.concatenate([points[:-1], points[1:]], axis=1)

        # TODO cleanup/pop/remove collection before update

        # Create the LineCollection object
        if lc is not None:
            lc.remove()
        lc = LineCollection(segments,
                            colors=colors,
                            linewidth=self.data_width,
                            linestyle=self.data_style)
        ax.add_collection(lc)

    # =====================================================
    # Button callbacks
    # =====================================================

    def start_plot(self):
        """Clear the graph and start recording."""
        self.x_time.clear()
        self.y_measured.clear()
        self.y2_measured.clear()
        self.start_time = time.monotonic()
        self.plotting = True

        self.line_measured.set_data([], [])
        self.line_interp.set_data([], [])

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
            if self.x_time:
                last_x = self.x_time[-1]
                self.start_time = time.monotonic() - last_x
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

        if self.api_loop is not None:
            try:
                self.api_loop.call_soon_threadsafe(lambda: None)
            except RuntimeError:
                pass

        self.destroy()


if __name__ == '__main__':
    app = MonitorWindow()
    app.mainloop()
