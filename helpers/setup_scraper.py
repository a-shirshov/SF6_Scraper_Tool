import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def setup_scraper(driver, username, password):
    # Ссылка на Sarpol - перекинет на страницу Авторизации
    driver.get("https://www.streetfighter.com/6/buckler/ru/auth/loginep?redirect_url=/profile/2457622556/battlelog")

    # Вроде ждём загрузки - надо наверное поменять, на динамическое ожидание
    time.sleep(3)

    # Locate the <select> element using XPath (Updated for Selenium 4.x)
    # Пример, как искать элемент - Здесь выбираем страну
    select_element = driver.find_element(By.XPATH, '//*[@id="country"]')
    select = Select(select_element)
    select.select_by_value("RU")

    Select(driver.find_element(By.XPATH, '//*[@id="birthMonth"]')).select_by_value("2")
    Select(driver.find_element(By.XPATH, '//*[@id="birthDay"]')).select_by_value("3")
    Select(driver.find_element(By.XPATH, '//*[@id="birthYear"]')).select_by_value("2000")

    # Все xpath лучше вынести в переменные - а то не понятно, что это такое + так легче переиспользовать
    driver.find_element(By.XPATH, "/html/body/div[2]/main/div/section/form/article/div/div[3]/div[1]/button").click()

    email_login_XPATH = '//*[@id="1-email"]'
    WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.XPATH, email_login_XPATH))
    )

    # Пишем креды
    login_field = driver.find_element(By.XPATH, email_login_XPATH)
    login_field.send_keys(username)

    password_field = driver.find_element(By.XPATH, '/html/body/div/div/div[2]/form/div/div/div/div/div[2]/div[2]/span/div/div/div/div/div/div/div/div/div[2]/div/div[2]/div/div/input')
    password_field.send_keys(password)

    # Ждём, что всё ввелось
    time.sleep(2)
    driver.find_element(By.XPATH, "/html/body/div/div/div[2]/form/div/div/div/button").click()

    #Ждём когда нас редиректнет с авторизации
    WebDriverWait(driver, 20).until(EC.url_contains("https://www.streetfighter.com/"))

    #Ловим кукисы - переходим на Sarpol
    driver.get("https://www.streetfighter.com/6/buckler/ru/profile/2457622556/play")
    try:
        cookie_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll"]'))
        )
        cookie_button.click()
        print("Cookie consent banner closed.")
    except:
        print("Cookie consent banner not found or already closed.")

    # Если не подождать, кукисы снова спросит - наверное, мы не успеваем их получить и быстро убегаем, если убрать
    time.sleep(2)
