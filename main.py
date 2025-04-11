from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from dotenv import load_dotenv
from datetime import datetime

import glob
import os
import shutil
import locale
import pandas as pd
import sys
import inspect
from time import sleep
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

# Configuración regional y de carpetas
os.environ['TZ'] = 'America/Santiago'
locale.setlocale(locale.LC_ALL, 'es_ES.UTF-8')
CSV_FOLDER = "declaraciones"
CSV_FILENAME = "meses_declarados.csv"
CSV_PATH = os.path.join(CSV_FOLDER, CSV_FILENAME)
os.makedirs(CSV_FOLDER, exist_ok=True)

class SiiAutomation:
    def __init__(self):
        self.driver = self._set_driver()
        self.wait = WebDriverWait(self.driver, 10)

    def _set_driver(self):
        options = Options()

        prefs = {
            "download.default_directory": os.path.abspath(CSV_FOLDER),
            "plugins.always_open_pdf_externally": True,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True
        }
        options.add_experimental_option("prefs", prefs)
        chrome_path = ChromeDriverManager().install()
        service = Service(chrome_path)
        return webdriver.Chrome(service=service, options=options)

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

    def _rename_latest_pdf(self, new_name, folder=CSV_FOLDER):
        sleep(2)  # Wait for download to finish
        list_of_files = glob.glob(os.path.join(folder, '*.pdf'))
        latest_file = max(list_of_files, key=os.path.getctime)

        new_path = os.path.join(folder, new_name)
        shutil.move(latest_file, new_path)
        print(f"Renamed {latest_file} to {new_path}")

    def _select_period(self):
        self.countdown(2)
        periodos = self.driver.find_element(By.ID, 'declaracionPeriodoMes')
        options = periodos.find_elements(By.TAG_NAME, 'option')
        now = datetime.now()
        past_month = now.month - 1 if now.month > 1 else 12
        month_name = datetime.strptime(str(past_month), "%m").strftime("%B")

        for opt in options:
            if opt.text.lower() == month_name.lower():
                periodos.click()
                self.wait.until(EC.visibility_of(opt)).click()
                break
        return month_name

    def _select_year(self):
        years = self.driver.find_element(By.CSS_SELECTOR, 'select[ng-model="declaracion.periodoAnioSeleccionado"]')
        options = years.find_elements(By.TAG_NAME, 'option')
        now = datetime.now()
        year = now.year if now.month > 1 else now.year - 1
        for opt in options:
            if opt.text == str(year):
                years.click()
                self.wait.until(EC.visibility_of(opt)).click()
                break
        return year

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
        file_name = f"Formulario_29_{month}_{year}.pdf"
        #rename file
        self._rename_latest_pdf(file_name)
        # Marcar como lista
        self._mark_declaration_as_done(folio_text, month, year)

    def _mark_declaration_as_done(self, folio, month, year):
        now = datetime.now()
        periodo = f"{month}-{year}"

        if not os.path.exists(CSV_PATH):
            df = pd.DataFrame(columns=["periodo", "fecha", "ready", "folio"])
        else:
            df = pd.read_csv(CSV_PATH)
        if not ((df["periodo"] == periodo) & (df["ready"] == "si")).any():
            df = pd.concat([
                df,
                pd.DataFrame([{
                    "periodo": periodo,
                    "fecha": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "ready": "si",
                    "folio": folio
                }])
            ], ignore_index=True)
            df.to_csv(CSV_PATH, index=False)
            print(f"📄 Registro guardado en CSV para el periodo: {periodo}")
        else:
            print("ℹ️ El periodo ya estaba registrado.")

    def F29_declaration(self, username):
        print("🌐 Iniciando declaración F29")
        self.driver.get("https://www4.sii.cl/propuestaf29ui/index.html#/default")
        month = self._select_period()
        year = self._select_year()
        self._submit_declaration()
        self._check_folio(month, year, username)

    def close(self):
        self.driver.quit()

def main():
    load_dotenv()
    username = os.getenv("USER_NAME_SPA")
    password = os.getenv("PASSWORD_SPA")

    sii_bot = SiiAutomation()
    sii_bot.login(
        url='https://zeusr.sii.cl//AUT2000/InicioAutenticacion/IngresoRutClave.html?https://misiir.sii.cl/cgi_misii/siihome.cgi',
        username=username,
        password=password
    )
    sii_bot.F29_declaration(username)
    sii_bot.close()

if __name__ == '__main__':
    main()
