from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from dotenv import dotenv_values
from datetime import datetime
from pathlib import Path

import csv
import os
import shutil
import sys
import inspect
import traceback
from time import sleep, time
import tkinter as tk
from tkinter import ttk, messagebox
import threading

# Carpeta de la app: junto al .exe cuando está compilada con cx_Freeze, si no junto a main.py
APP_DIR = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
DECLARACIONES_DIR = APP_DIR / "declaraciones"
CSV_FILENAME = "meses_declarados.csv"
LOGIN_URL = 'https://zeusr.sii.cl//AUT2000/InicioAutenticacion/IngresoRutClave.html?https://misiir.sii.cl/cgi_misii/siihome.cgi'
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

if sys.stdout is None:
    # El .exe no tiene consola: los print y errores quedan en un log junto a la app
    sys.stdout = sys.stderr = open(APP_DIR / "sii_bot.log", "a", encoding="utf-8", buffering=1)
else:
    sys.stdout.reconfigure(encoding='utf-8')


def periodo_anterior():
    """Mes y año que corresponde declarar hoy (el F29 de un mes se declara al mes siguiente)."""
    now = datetime.now()
    if now.month == 1:
        return MESES[-1], now.year - 1
    return MESES[now.month - 2], now.year


def normalizar_rut(rut):
    """Devuelve el RUT como 12345678-9, o None si el dígito verificador no corresponde."""
    rut = rut.replace(".", "").replace("-", "").replace(" ", "").upper()
    cuerpo, dv = rut[:-1], rut[-1:]
    if not cuerpo.isdigit():
        return None
    resto = 11 - sum(int(d) * f for d, f in zip(reversed(cuerpo), [2, 3, 4, 5, 6, 7] * 2)) % 11
    dv_esperado = {11: "0", 10: "K"}.get(resto, str(resto))
    return f"{cuerpo}-{dv}" if dv == dv_esperado else None


class SiiAutomation:
    def __init__(self, download_dir):
        self.download_dir = download_dir
        self.started_at = time()
        self.driver = self._set_driver()
        self.wait = WebDriverWait(self.driver, 10)

    def _set_driver(self):
        options = Options()

        prefs = {
            "download.default_directory": str(self.download_dir),
            "plugins.always_open_pdf_externally": True,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True
        }
        options.add_experimental_option("prefs", prefs)
        # Selenium Manager descarga el chromedriver que corresponde al Chrome instalado
        return webdriver.Chrome(options=options)

    def countdown(self, t):
        caller = inspect.currentframe().f_back.f_code.co_name
        for i in range(t, 0, -1):
            sys.stdout.write(f"\r{caller} - Tiempo restante: {i} segundos")
            sys.stdout.flush()
            sleep(1)
        sys.stdout.write("\n")

    def login(self, url, username, password):
        self.driver.get(url)
        self.wait.until(EC.visibility_of_element_located((By.ID, "rutcntr"))).send_keys(username)
        self.driver.find_element(By.ID, "clave").send_keys(password)
        self.driver.find_element(By.ID, "bt_ingresar").click()
        self.countdown(2)

    def _rename_latest_pdf(self, new_name):
        sleep(2)  # Wait for download to finish
        # Solo PDFs bajados en esta ejecución: si el mes ya estaba declarado no se descarga nada
        new_files = [f for f in self.download_dir.glob('*.pdf') if f.stat().st_ctime >= self.started_at]
        if not new_files:
            print("ℹ️ No se descargó un certificado nuevo.")
            return
        latest_file = max(new_files, key=lambda f: f.stat().st_ctime)

        new_path = self.download_dir / new_name
        shutil.move(latest_file, new_path)
        print(f"Renamed {latest_file} to {new_path}")

    def _select_period(self, month_name):
        self.countdown(2)
        periodos = self.driver.find_element(By.ID, 'declaracionPeriodoMes')
        options = periodos.find_elements(By.TAG_NAME, 'option')

        for opt in options:
            if opt.text.lower() == month_name.lower():
                periodos.click()
                self.wait.until(EC.visibility_of(opt)).click()
                return
        raise RuntimeError(f"El SII no ofrece {month_name} como período a declarar.")

    def _select_year(self, year):
        years = self.driver.find_element(By.CSS_SELECTOR, 'select[ng-model="declaracion.periodoAnioSeleccionado"]')
        options = years.find_elements(By.TAG_NAME, 'option')

        for opt in options:
            if opt.text == str(year):
                years.click()
                self.wait.until(EC.visibility_of(opt)).click()
                return
        raise RuntimeError(f"El SII no ofrece el año {year} como período a declarar.")

    def _submit_declaration(self):
        self.countdown(2)
        try:
            self.driver.find_element(By.XPATH, '//*[@id="my-wrapper"]/div[2]/div[1]/div[2]/div/div/div/div[2]/form/div[2]/div/div[3]/button').click()
            self.countdown(5)
            try:
                self.driver.find_element(By.XPATH, '/html/body/div[1]/div/div/div/div[3]/button').click()
            except:
                pass
            self.countdown(5)
            self.driver.find_element(By.XPATH, '//*[@id="my-wrapper"]/div[2]/div[1]/div[2]/div/div/div[2]/div[3]/div[1]/button').click()
            self.countdown(7)
            self.driver.find_element(By.XPATH, '/html/body/div[1]/div/div/div/div[3]/button[2]').click()
            print("✅ Declaración enviada correctamente.")
            self.countdown(10)

        except Exception as e:
            print("Este mes ya fue declarado o ocurrió un error:", e)

    def _check_folio(self,month, year, username):
        self.driver.get("https://www4.sii.cl/rfiInternet/consulta/index.html#rfiSelFormularioPeriodo")
        self.countdown(4)
        #select form type
        form_type = self.driver.find_element(By.XPATH, '//*[@id="item-form"]/select')
        form_type.click()
        #select the option with text Formulario 29
        form29_option = self.driver.find_element(By.XPATH, '//*[@id="item-form"]/select/option[2]')
        form29_option.click()
        #select for year
        year_select = self.driver.find_element(By.XPATH, '//*[@id="item-form"]/select[1]')
        year_options = year_select.find_elements(By.TAG_NAME, 'option')
        for opt in year_options:
            if opt.text == str(year):
                year_select.click()
                self.wait.until(EC.visibility_of(opt)).click()
                break
        #select for month
        month_select = self.driver.find_element(By.XPATH, '//*[@id="item-form"]/select[2]')
        month_options = month_select.find_elements(By.TAG_NAME, 'option')
        for opt in month_options:
            if opt.text.lower() == month.lower():
                month_select.click()
                self.wait.until(EC.visibility_of(opt)).click()
                break
        #click on search button
        search_button = self.driver.find_element(By.XPATH, '//*[@id="item-form"]/table/tbody/tr/td/table/tbody/tr/td/button')
        search_button.click()
        self.countdown(2)
        folio= self.driver.find_element(By.XPATH, '//*[@id="main"]/table/tbody/tr/td/table/tbody/tr[7]/td/div/div[2]/table[1]/tbody/tr[3]/td[1]/div/a')
        folio_text = folio.text
        print(f"Folio: {folio_text}")
        #click on folio link
        # folio.click()
        # /html/body/div[6]/div/table/tbody/tr[2]/td[2]/div/table/tbody/tr/td/table/tbody/tr[8]/td/table/tbody/tr/td/table/tbody/tr/td[3]/button
        # self.countdown(2)
        # ver_certificado_button = self.driver.find_element(By.XPATH, '/html/body/div[6]/div/table/tbody/tr[2]/td[2]/div/table/tbody/tr/td/table/tbody/tr[8]/td/table/tbody/tr/td/table/tbody/tr/td[3]/button')
        # ver_certificado_button.click()
        # self.countdown(10)
        # username_cleaned = username.split("-")[0]
        # #create link
        # link = f"https://www4.sii.cl/rfiInternet/formSolemne?folio={folio_text}&rut={username_cleaned}&dv=0&form=029"
        # self.driver.get(link)
        # self.countdown(8)
        #wait for download to finish
        file_name = f"Formulario_29_{month.lower()}_{year}.pdf"
        #rename file
        self._rename_latest_pdf(file_name)
        # Marcar como lista
        self._mark_declaration_as_done(folio_text, month, year)
        return folio_text

    def _mark_declaration_as_done(self, folio, month, year):
        periodo = f"{month.lower()}-{year}"
        csv_path = self.download_dir / CSV_FILENAME
        nuevo = not csv_path.exists()

        if not nuevo:
            with open(csv_path, newline="", encoding="utf-8") as f:
                if any(r["periodo"] == periodo and r["ready"] == "si" for r in csv.DictReader(f)):
                    print("ℹ️ El periodo ya estaba registrado.")
                    return

        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if nuevo:
                writer.writerow(["periodo", "fecha", "ready", "folio"])
            writer.writerow([periodo, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "si", folio])
        print(f"📄 Registro guardado en CSV para el periodo: {periodo}")

    def F29_declaration(self, username, month, year):
        print("🌐 Iniciando declaración F29")
        self.driver.get("https://www4.sii.cl/propuestaf29ui/index.html#/default")
        try:
            self.wait.until(EC.presence_of_element_located((By.ID, 'declaracionPeriodoMes')))
        except TimeoutException:
            raise RuntimeError("No se pudo abrir el F29 en el SII. Revisa que el RUT y la clave sean correctos.") from None
        self._select_period(month)
        self._select_year(year)
        self._submit_declaration()
        return self._check_folio(month, year, username)

    def close(self):
        self.driver.quit()

class SiiBotApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SII Bot - Declaración F29")
        self.root.resizable(False, False)

        self.create_widgets()

        # Center window
        self.root.eval('tk::PlaceWindow . center')

    def create_widgets(self):
        style = ttk.Style()
        style.configure('TButton', font=('Helvetica', 10), padding=5)
        style.configure('TLabel', font=('Helvetica', 10))
        style.configure('Title.TLabel', font=('Helvetica', 14, 'bold'))

        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main_frame, text="Bot SII F29 sin movimiento", style='Title.TLabel').pack(pady=(0, 20))

        # Credenciales (se rellenan solas si hay un .env junto a la app)
        env = dotenv_values(APP_DIR / ".env")
        frame_cred = ttk.Frame(main_frame)
        frame_cred.pack(fill=tk.X, pady=(0, 20))
        frame_cred.columnconfigure(1, weight=1)

        ttk.Label(frame_cred, text="RUT:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10), pady=3)
        self.entry_rut = ttk.Entry(frame_cred)
        self.entry_rut.grid(row=0, column=1, sticky=tk.EW, pady=3)
        self.entry_rut.insert(0, env.get("USER_NAME_SPA") or "")

        ttk.Label(frame_cred, text="Clave SII:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=3)
        self.entry_clave = ttk.Entry(frame_cred, show="•")
        self.entry_clave.grid(row=1, column=1, sticky=tk.EW, pady=3)
        self.entry_clave.insert(0, env.get("PASSWORD_SPA") or "")

        # Current Month Option
        mes, anio = periodo_anterior()
        self.btn_current = ttk.Button(main_frame, text=f"Rendir Declaración {mes} {anio}",
                                      command=lambda: self.start(mes, anio))
        self.btn_current.pack(fill=tk.X, pady=(0, 20))

        ttk.Separator(main_frame, orient='horizontal').pack(fill=tk.X, pady=10)

        # Specific Month Option
        ttk.Label(main_frame, text="O rendir mes específico de forma retroactiva:").pack(pady=(10, 5))

        frame_combos = ttk.Frame(main_frame)
        frame_combos.pack(fill=tk.X, pady=5)

        # Month Combo
        self.combo_month = ttk.Combobox(frame_combos, values=MESES, state="readonly", width=15)
        self.combo_month.pack(side=tk.LEFT, padx=(0, 10), expand=True)
        self.combo_month.set(mes)

        # Year Combo
        current_year = datetime.now().year
        years = [str(y) for y in range(current_year - 5, current_year + 1)]
        self.combo_year = ttk.Combobox(frame_combos, values=years, state="readonly", width=10)
        self.combo_year.pack(side=tk.LEFT, expand=True)
        self.combo_year.set(str(anio))

        self.btn_specific = ttk.Button(main_frame, text="Rendir Mes Seleccionado",
                                       command=lambda: self.start(self.combo_month.get(), self.combo_year.get()))
        self.btn_specific.pack(fill=tk.X, pady=(15, 0))

        # Status
        self.status_var = tk.StringVar()
        self.status_var.set("Listo")
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var, foreground="blue")
        self.status_label.pack(side=tk.BOTTOM, pady=15)

    def set_buttons_state(self, state):
        self.btn_current.configure(state=state)
        self.btn_specific.configure(state=state)

    def show_message(self, title, message, is_error=False):
        if is_error:
            messagebox.showerror(title, message)
        else:
            messagebox.showinfo(title, message)

    def show_success(self, month, year, folio, folder):
        message = f"Declaración F29 de {month} {year} lista (folio {folio}).\n\nLos archivos quedaron en:\n{folder}"
        if not hasattr(os, "startfile"):  # solo existe en Windows
            self.show_message("Éxito", message)
        elif messagebox.askyesno("Éxito", message + "\n\n¿Abrir la carpeta?"):
            os.startfile(folder)

    def start(self, month, year):
        rut = normalizar_rut(self.entry_rut.get())
        password = self.entry_clave.get()
        if not rut or not password:
            self.show_message("Error", "Ingresa un RUT válido (ej: 12345678-9) y tu clave del SII.", True)
            return

        self.set_buttons_state('disabled')
        self.status_var.set("Ejecutando bot... Por favor espere.")
        threading.Thread(target=self.run_bot, args=(rut, password, month, year), daemon=True).start()

    def run_bot(self, username, password, month, year):
        # Una carpeta por RUT para no mezclar certificados de distintas empresas
        folder = DECLARACIONES_DIR / username
        sii_bot = None
        try:
            folder.mkdir(parents=True, exist_ok=True)
            sii_bot = SiiAutomation(folder)
            sii_bot.login(url=LOGIN_URL, username=username, password=password)
            folio = sii_bot.F29_declaration(username, month, year)

            self.root.after(0, lambda: self.status_var.set("Proceso completado exitosamente."))
            self.root.after(0, lambda: self.show_success(month, year, folio, folder))

        except Exception as e:
            traceback.print_exc()
            # Los errores de Selenium traen un stacktrace de chromedriver; basta con el mensaje
            error = getattr(e, "msg", None) or str(e)
            self.root.after(0, lambda: self.status_var.set("Error durante la ejecución."))
            self.root.after(0, lambda: self.show_message("Error", f"Ocurrió un error:\n{error}", True))
        finally:
            if sii_bot:
                sii_bot.close()
            self.root.after(0, lambda: self.set_buttons_state('normal'))

def main():
    root = tk.Tk()
    app = SiiBotApp(root)
    root.mainloop()

if __name__ == '__main__':
    main()
