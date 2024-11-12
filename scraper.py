from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from dataclasses import dataclass
import pandas as pd
from openpyxl import load_workbook
from selenium.common.exceptions import TimeoutException
import getpass
import re
from openpyxl.styles import PatternFill


@dataclass
class Player:
    name: str
    cfn: str
    phases: dict
    matches: list

# Чтение кредов - ввод пароля спрятан  - если вдруг на стрие будет запуск - 
# для разработки можно не включать и захардкодить креды - либо сделать чтение из файла
def get_credentials():
    """Запрашивает логин и пароль у пользователя через консоль."""
    username = input("Введите логин: ")
    password = getpass.getpass("Введите пароль: ")
    return username, password

# Function to highlight a row in red
def highlight_row_red(worksheet, row_number, num_columns):
    light_red_fill = PatternFill(start_color="FFCCCC", end_color="FFCCCC", fill_type="solid")  # Light red color
    worksheet.cell(row=row_number, column=1).fill = light_red_fill  # Column 1 corresponds to 'Player Name'

# Function to check if a player should be highlighted
def should_highlight_player(total_matches, rating_name, min_matches, max_matches, max_rating):
    if min_matches is not None and total_matches < min_matches:
        return True
    if max_matches is not None and total_matches > max_matches:
        return True
    if max_rating is not None and rating_name > max_rating:
        return True
    return False

def get_criteria_from_user():
    """Запрашивает у пользователя критерии для проверки игроков. Пользователь может пропустить любое поле."""
    try:
        min_matches = input("Введите минимальное количество матчей (x) или оставьте пустым для пропуска: ")
        max_matches = input("Введите максимальное количество матчей (y) или оставьте пустым для пропуска: ")
        max_rating = input("Введите максимально допустимый рейтинг (например, 'Diamond 1') или оставьте пустым для пропуска: ")
        
        # Преобразуем введенные значения в числовые, если они указаны
        min_matches = int(min_matches) if min_matches else None
        max_matches = int(max_matches) if max_matches else None
        max_rating = max_rating if max_rating else None
        
        return min_matches, max_matches, max_rating
    except ValueError:
        print("Ошибка ввода. Убедитесь, что вы вводите числовые значения для количества матчей.")
        return None, None, None

# На сайте рейтинг картинкой - это самое умное и простое имхо
rating_thresholds = [
    (25_000, "Master"),
    (23_800, "Diamond 5"),
    (22_600, "Diamond 4"),
    (21_400, "Diamond 3"),
    (20_200, "Diamond 2"),
    (19_000, "Diamond 1"),
    (17_800, "Platinum 5"),
    (16_600, "Platinum 4"),
    (15_400, "Platinum 3"),
    (14_200, "Platinum 2"),
    (13_000, "Platinum 1"),
    (12_200, "Gold 5"),
    (11_400, "Gold 4"),
    (10_600, "Gold 3"),
    (9_800,  "Gold 2"),
    (0,      "Gold 1")  # Default rating for LPs below 9800
]

def get_rating_name(lp):
    try:
        cleaned_lp = lp.replace(" ", "")
        cleaned_lp = cleaned_lp[:len(cleaned_lp)-2]
        lp_value = int(cleaned_lp)
    except (ValueError, AttributeError) as e:
        return "Unknown"

    for threshold, rating in rating_thresholds:
        if lp_value >= threshold:
            return rating

    return "Unknown"

bad_players = []

def scrape_player_data(driver, cfn):
    try:
        cfn_int = int(cfn)
        print(cfn_int)
    except ValueError:
        bad_players.append(cfn)
        print(f'Not a cfn: {cfn}')
        return
    driver.get(f"https://www.streetfighter.com/6/buckler/ru/profile/{cfn}/play")
    
    #Вот тут xpath вынесен и понятно, что ищем
    player_name_xpath = '/html/body/div[1]/div/article[2]/div/div[1]/section/ul/li[2]/span[2]'
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.XPATH, player_name_xpath))
    )
    player_name = driver.find_element(By.XPATH, player_name_xpath).text

    # Ждём плашки league points
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.XPATH, '/html/body/div[1]/div/article[3]/div/div[1]/aside[1]/div/ul/li[2]'))
    )
    driver.find_element(By.XPATH, "/html/body/div[1]/div/article[3]/div/div[1]/aside[1]/div/ul/li[2]").click()

    # Могут быть загрузки - это ждём пока уйдёт квадратик загрузки
    try:
        WebDriverWait(driver, 30).until(
            EC.invisibility_of_element_located((By.XPATH, "//*[contains(@class, 'play_loader__')]"))  # Wait for loader to disappear
        )
    except TimeoutException:
        print(f"Timeout waiting for loader to disappear for player {cfn}. Continuing anyway...")

    # Здесь фазы смотрим - лучшее за всё время вроде имеет значение -1, а последняя фаза самое большое
    # В html можно посмотреть - ждать все фазы при большом кол-ве игроков
    select_xpath = '/html/body/div[1]/div/article[3]/div/div[1]/aside[2]/div/dl/dd/select'
    select_element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, select_xpath))
    )
    
    # Scroll into view to avoid interception - я не помню, зачем - просто скроллимся вниз - может данные без этого не достать
    driver.execute_script("arguments[0].scrollIntoView();", select_element)
    
    # Wait until the select element is clickable
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, select_xpath))
    )
    
    phase_select = Select(select_element)

    # Dictionary to store data for each phase
    phases = {}

    # Iterate over each option
    for option in phase_select.options:
        # лучшее за всё время вроде имеет значение -1, а последняя фаза самое большое
        # Вот value за это отвечает
        option_value = option.get_attribute("value")
        phase = option.text  # Get phase name

        # Select the phase
        phase_select.select_by_value(option_value)

        # Могут быть загрузки - это ждём пока уйдёт квадратик загрузки
        try:
            WebDriverWait(driver, 30).until(
                EC.invisibility_of_element_located((By.XPATH, "//*[contains(@class, 'play_loader__')]"))  # Wait for loader to disappear
            )
        except TimeoutException:
            print(f"Timeout waiting for loader to disappear for player {cfn}. Continuing anyway...")

        # Ждём таблицу 
        try:
            ul_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '/html/body/div[1]/div/article[3]/div/div[1]/article/div/ul'))
            )
        except TimeoutException:
            # Если вылезли кукисы - они не дают сканировать - вроде баг пофиксился через time.sleep в конце setup_scraper,наверное можно убрать 
            try:
                cookie_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll"]'))
                )
                cookie_button.click()
                print("Cookie consent banner closed.")
            except:
                print("Cookie consent banner not found or already closed.")

        #Берём топ 3 персонажа
        li_elements = ul_element.find_elements(By.TAG_NAME, "li")[:3]

        # Забираем данные
        top_league_point_names = []
        top_league_point_lps = []
        for li in li_elements:
            league_point_name = li.find_element(By.XPATH, './/p[contains(@class, "league_point_name")]').text
            league_point_lp = li.find_element(By.XPATH, './/p[contains(@class, "league_point_lp")]').text
            top_league_point_names.append(league_point_name)
            top_league_point_lps.append(league_point_lp)

        phases[phase] = list(zip(top_league_point_names, top_league_point_lps))

    # Здесь можно добавить секцию результаты
    # Можно разбить на подфункции

    results_button_xpath  = '/html/body/div[1]/div/article[3]/div/div[1]/aside[1]/div/ul/li[7]'
    results_button = WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.XPATH, results_button_xpath))
    )
    results_button.click()

    section_matches_xpath = '/html/body/div[1]/div/article[3]/div/div[1]/article/div[3]/div/section[1]'
    section_matches = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, section_matches_xpath))
    )

    matches_data = []
    matches_elements = section_matches.find_elements(By.TAG_NAME, "dl")
    for matches_element in matches_elements:
        matches_str = matches_element.find_element(By.XPATH, './/span[contains(@class, "battle_style_count")]').text
        matches = int(re.sub(r'\D+', '', matches_str))
        matches_data.append(matches)

    #Возвращаем структуру
    return Player(
        name=player_name,
        cfn=cfn,
        phases=phases,
        matches=matches_data
    )

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

    # Вроде ждём загрузки - надо наверное поменять, на динамическое ожидание, если получится
    time.sleep(2)

    # Пишем креды
    login_field = driver.find_element(By.XPATH, '//*[@id="1-email"]')
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

def read_cfn_from_file(filename):
    """Чтение CFN имен из текстового файла. Один CFN на строку."""
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            cfn_list = [line.strip() for line in file if line.strip()]  # Убираем пустые строки и пробелы
        return cfn_list
    except FileNotFoundError:
        print(f"Файл '{filename}' не найден.")
        return []
    except Exception as e:
        print(f"Произошла ошибка при чтении файла: {e}")
        return []

def read_cfn_from_csv(filename):
    df_players = pd.read_csv(filename)
    players_list = df_players["CFN ЧИСЛОВОЙ Код игрока"].to_list()
    return players_list

# ОСНОВНОЙ КОД ПРОГРАММЫ - Я ХЗ КАК MAIN В PYTHON сделать 

filename =  r".\cfn_list.txt"
players_cfn = read_cfn_from_csv(".\kingofplat4-2024-11-11.csv")
if players_cfn:
    print("CFN успешно загружены:")
    print(players_cfn)
else:
    print("Список CFN пуст или произошла ошибка.")

min_matches, max_matches, max_rating = get_criteria_from_user()


# Set up the path to geckodriver if it's not in your system's PATH
geckodriver_path = r".\geckodriver.exe"  # Replace with the actual path on Windows
service = Service(geckodriver_path)

username, password = get_credentials()
# Initialize the Firefox WebDriver
driver = webdriver.Firefox(service=service)
setup_scraper(driver, username, password)
    
# Дальнейшая работа с players_cfn
players_data = []
for cfn in players_cfn:
    player_data = scrape_player_data(driver, cfn)
    if player_data != None:
        players_data.append(player_data)
    #time.sleep(10000)

#Завершаем работу - для дебага можно писать большой time.Sleep(), чтобы походить и взять xpath и прочее
driver.quit()

df = pd.DataFrame(bad_players, columns=["Wrong CFN"])
df.to_csv('bad_players.csv', index=False)

#EXCEL
#Подготовка к работе с excel - здесь gpt помог сильно 
data = []
for player in players_data:
    for phase, character_data in player.phases.items():
        for i, (char_name, lp) in enumerate(character_data):
            rating_name = get_rating_name(lp)  # Get the rating name based on the LP
            data.append({
                'Player Name': player.name if i == 0 else "",  # Merge player name for the first row
                'CFN': player.cfn if i == 0 else "",  # Merge CFN for the first row
                'Phase': phase if i == 0 else "",  # Merge phase for the first row
                'League Point Name': char_name,
                'League Point LP': lp,
                'Rating Name': rating_name,  # Add the rating name column
                'Ranked Matches': player.matches[0],
                'Casual Matches': player.matches[1],
                'Room Matches': player.matches[2],
                'Battlehub Matches': player.matches[3]
            })

# Дальше gpt - я не прокоментирую сильно - есть комменты на английском

# Create the DataFrame from the data list
df = pd.DataFrame(data)

# Define the Excel filename
excel_filename = "players_league_points_phases_with_rating.xlsx"

# Save the DataFrame to an Excel file
df.to_excel(excel_filename, index=False)

# Now, let's merge cells for each player's CFN and Player Name in the Excel file
workbook = load_workbook(excel_filename)
worksheet = workbook.active

num_columns = len(df.columns)

# Keep track of the starting row for each player and merge cells
current_row = 2  # Since row 1 has headers, start from the second row
for player in players_data:
    total_matches = player.matches[0] + player.matches[1] + player.matches[2] + player.matches[3]
    rating_name = get_rating_name(lp)  # Calculate rating again for highlighting

    # Check if the player should be highlighted
    #highlight = should_highlight_player(total_matches, rating_name, min_matches, max_matches, max_rating)
    # Get the total number of rows for this player's data
    num_phases = sum(len(character_data) for phase, character_data in player.phases.items())

    # if highlight:
    #         for row in range(current_row, current_row + num_phases):
    #             highlight_row_red(worksheet, row, num_columns)

    # Merge Player Name cells (Column A)
    worksheet.merge_cells(f'A{current_row}:A{current_row + num_phases - 1}')
    # Merge CFN cells (Column B)
    worksheet.merge_cells(f'B{current_row}:B{current_row + num_phases - 1}')

    worksheet.merge_cells(f'G{current_row}:G{current_row + num_phases - 1}')
    worksheet.merge_cells(f'H{current_row}:H{current_row + num_phases - 1}')
    worksheet.merge_cells(f'I{current_row}:I{current_row + num_phases - 1}')
    worksheet.merge_cells(f'J{current_row}:J{current_row + num_phases - 1}')
    
    # Move to the next player's data
    current_row += num_phases

# Save the workbook after merging
workbook.save(excel_filename)

print(f"Data saved to {excel_filename} with merged cells for Player Names, CFNs, and Rating Names.")