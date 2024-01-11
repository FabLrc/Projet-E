import json
import time
import logging
import sys
import requests
import os
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException, StaleElementReferenceException
from logging.handlers import RotatingFileHandler

# Configuration de la journalisation pour écrire à la fois dans un fichier et sur la console
log_format = "%(asctime)s - %(levelname)s - %(message)s"

# Création d'un logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Handler pour écrire dans le fichier log
file_handler = RotatingFileHandler('engie_automation.log', maxBytes=1000000, backupCount=5)
file_handler.setFormatter(logging.Formatter(log_format))
logger.addHandler(file_handler)

# Handler pour écrire sur la console
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter(log_format))
logger.addHandler(console_handler)

def update_script():
    url = "https://raw.githubusercontent.com/username/repository/master/your_script.py" # Lien vers la version brute de votre script sur GitHub
    response = requests.get(url)
    
    if response.status_code == 200:
        with open(__file__, 'r') as file:
            current_script = file.read()
        
        if current_script != response.text:
            with open(__file__, 'w') as file:
                file.write(response.text)
            print("Le script a été mis à jour. Veuillez le relancer.")
            os._exit(0)
    else:
        print("Impossible de vérifier la mise à jour.")

if __name__ == "__main__":
    update_script()

# Lecture de la configuration
try:
    with open('config.json') as config_file:
        config = json.load(config_file)
    site_url = "https://www.moncomptetravaux.engie.fr/partenaire/projets/disponibles"
    username = config['username']
    password = config['password']
except Exception as e:
    logging.error(f"Erreur lors de la lecture de la configuration : {e}")
    raise

# Fonctions modulaires
def initialize_driver():
    try:
        driver = webdriver.Chrome()
        logging.info("Navigateur ouvert avec succès.")
        return driver
    except WebDriverException as e:
        logging.error(f"Erreur lors de l'initialisation du WebDriver : {e}")
        raise

def login(driver, username, password):
    try:
        driver.get(site_url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "pro_login_email"))).send_keys(username)
        driver.find_element(By.ID, "pro_login_password").send_keys(password)
        driver.find_element(By.XPATH, "//button[contains(., 'Connexion')]").click()
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "tr")))
        logging.info("Connexion réussie.")
    except Exception as e:
        logging.error(f"Erreur lors de la connexion : {e}")
        raise

def has_new_label(project_row):
    try:
        new_label = project_row.find_element(By.CLASS_NAME, "label-color")
        return "new" in new_label.text.lower()
    except NoSuchElementException:
        return False

def accept_new_projects(driver):
    try:
        while True:
            project_rows = WebDriverWait(driver, 5).until(EC.presence_of_all_elements_located((By.TAG_NAME, "tr")))
            new_projects_found = any(has_new_label(row) for row in project_rows)

            if new_projects_found:
                for row in project_rows:
                    if has_new_label(row):
                        row.find_element(By.TAG_NAME, "a").click()

                        # Vérifier si le message d'erreur est affiché
                        try:
                            error_message = WebDriverWait(driver, 5).until(
                                EC.presence_of_element_located((By.XPATH, "//div[contains(text(), \"Il vous est impossible d'accepter ce projet.\")]"))
                            )
                            logging.info("Le projet ne peut pas être accepté. Retour à la liste des projets.")
                            driver.get(site_url)
                            break
                        except TimeoutException:
                            # Pas de message d'erreur, on continue
                            pass

                        # Cliquer sur le bouton Accepter si disponible
                        try :
                            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Accepter')]"))).click()
                            logging.info("Nouveau projet accepté.")
                            driver.get(site_url)
                            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, "tr")))
                            break
                        except TimeoutException:
                            logging.error("L'élément n'a pas été trouvé dans le délai imparti. Retour à l'accueil.")
                            driver.get(site_url)
                            logging.info("Raffraichissement du driver.")
                            driver.refresh()
                            # Gestion supplémentaire (par exemple, rafraîchir la page ou passer à une autre action)
            else:
                break
    except Exception as e:
        logging.error(f"Erreur lors de l'acceptation des nouveaux projets : {type(e).__name__}, {e}")

        try:
            driver.get(site_url)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "tr")))
            logging.info("Retour à la liste des projets après l'erreur.")
        except Exception as e_inner:
            logging.error(f"Erreur lors du retour à la liste des projets : {type(e_inner).__name__}, {e_inner}")

def main():
    driver = initialize_driver()
    try:
        login(driver, username, password)

        while True:
            current_time = datetime.now()
            if 9 <= current_time.hour < 20:
                accept_new_projects(driver)

                next_check_time = current_time.replace(second=0, microsecond=0, minute=2) + timedelta(hours=1)
                time_until_next_check = (next_check_time - current_time).total_seconds()
                logging.info(f"Aucun nouveau projet trouvé. Prochaine vérification à {next_check_time.strftime('%H:%M:%S')}.")
                time.sleep(time_until_next_check)
                driver.refresh()
                time.sleep(30)
            else:
                time.sleep(60)
    except Exception as e:
        logging.error(f"Erreur dans la boucle principale : {e}")
    finally:
        driver.quit()
        logging.info("Navigateur fermé.")

if __name__ == "__main__":
    main()