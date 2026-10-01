# Source - https://stackoverflow.com/a/74561156
# Posted by aVral, modified by community. See post 'Timeline' for change history
# Retrieved 2026-10-01, License - CC BY-SA 4.0

import matplotlib.pyplot as plt
import numpy as np
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from tkinter import ttk

x_data, y_data = [], []

class Win(tk.Tk):

    def __init__(self):
    
        super().__init__()
    
        self.title('I-V liveplot')
        self.geometry('500x450')

        # Frame that holds wigets on the left side
        left_frame = ttk.Frame(self)
        left_frame.pack(side= "left", padx =10, pady = 10)  #, fill="y", expand=True
     
        self.fig = plt.figure(figsize=(4, 3.5), dpi=100)
        self.ax = self.fig.add_subplot(1,1,1)
        self.line, = self.ax.plot([0], [0])
        self.ax.set_xlabel('Voltage / V', fontsize = 12)
        self.ax.set_ylabel('Current / A', fontsize = 12)
        self.fig.tight_layout()
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self)
        self.canvas.get_tk_widget().pack(side= tk.BOTTOM)
    
    
        voltage_range_label = tk.Label(left_frame, text = "Voltage range")
        voltage_range_label.pack(side = "top", padx =10, pady =2)
        self.voltage_range = tk.IntVar()
        self.voltage_range.set(10)
        voltage_range_spinbox = ttk.Spinbox(left_frame, from_=-3e2, to = 5e2, textvariable = self.voltage_range, width=8)
        voltage_range_spinbox.pack(side="top", padx =10, pady =5)
    
        voltage_step_label = tk.Label(left_frame, text = "Step")
        voltage_step_label.pack(side = "top", padx =10, pady =2)
        self.step = tk.IntVar()
        self.step.set(1)
        step_spinbox = ttk.Spinbox(left_frame, from_=-3e2, to = 5e2, textvariable = self.step, width =9)
        step_spinbox.pack(side="top", padx =10, pady =5)
    
        self.start = tk.BooleanVar(value = False)
        start_butt = ttk.Button(left_frame, text="Start", command= lambda: self.start.set(True))
        start_butt.pack(side='top', padx =10, pady =10)
         
        stop_butt = ttk.Button(left_frame, text="Resume", command=lambda: self.is_paused.set(False))
        stop_butt.pack(side="top", padx =10, pady =10)    
    
        self.is_paused = tk.BooleanVar()  # variable to hold the pause/resume state
        restart_butt = ttk.Button(left_frame, text="Pause", command=lambda: self.is_paused.set(True))
        restart_butt.pack(side="top", padx =10, pady =10)

    def update(self, k=1):

        if self.start.get() and not self.is_paused.get(): 

            # quasi For Loop
            idx = [i for i in range(0, k, self.step.get())][-1]
            x_data.append(idx)
            y_data.append(np.sin(idx/5))
            self.line.set_data(x_data, y_data)
            self.fig.gca().relim()
            self.fig.gca().autoscale_view()
            self.canvas.draw()
            #self.canvas.flush_events()
            k += self.step.get()[![enter image description here][2]][2]
         
        if k <= self.voltage_range.get():
        
            self.after(1000, self.update, k)


if __name__ == "__main__":
    app = Win()
    app.after(1000, app.update)
    app.mainloop()
