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
import os
from dotenv import load_dotenv
from selenium.common.exceptions import NoSuchElementException
from openpyxl.utils import get_column_letter

load_dotenv()

@dataclass
class Player:
    name: str
    cfn: str
    phases: dict
    matches: list
    max_lp: int

# Function to highlight a row in red
def highlight_row_red(worksheet, row_number, num_columns):
    light_red_fill = PatternFill(start_color="FFCCCC", end_color="FFCCCC", fill_type="solid")  # Light red color
    worksheet.cell(row=row_number, column=1).fill = light_red_fill  # Column 1 corresponds to 'Player Name'

# Function to check if a player should be highlighted
def should_highlight_player(total_matches, max_lp, min_matches, max_matches, max_rating):
    if min_matches is not None and total_matches < min_matches:
        return True
    if max_matches is not None and total_matches > max_matches:
        return True
    if max_rating is not None and max_lp > max_rating:
        return True
    return False

def get_criteria_from_user():
    """Запрашивает у пользователя критерии для проверки игроков. Пользователь может пропустить любое поле."""
    try:
        min_matches = input("Введите минимальное количество раундов (x) или оставьте пустым для пропуска: ")
        max_matches = input("Введите максимальное количество раундов (y) или оставьте пустым для пропуска: ")
        max_rating = input("Введите максимально допустимое кол-во очков (например, 19000) или оставьте пустым для пропуска: ")
        
        # Преобразуем введенные значения в числовые, если они указаны
        min_matches = int(min_matches) if min_matches else None
        max_matches = int(max_matches) if max_matches else None
        max_rating =  int(max_rating) if max_rating else None
        
        return min_matches, max_matches, max_rating
    except ValueError:
        print("Ошибка ввода. Убедитесь, что вы вводите числовые значения для количества матчей.")
        return None, None, None

# На сайте рейтинг картинкой - это самое умное и простое имхо
rank_thresholds = {
    "Rookie 1": 0, "Rookie 2": 200, "Rookie 3": 400, "Rookie 4": 600, "Rookie 5": 800,
    "Iron 1": 1000, "Iron 2": 1400, "Iron 3": 1800, "Iron 4": 2200, "Iron 5": 2600,
    "Bronze 1": 3000, "Bronze 2": 3400, "Bronze 3": 3800, "Bronze 4": 4200, "Bronze 5": 4600,
    "Silver 1": 5000, "Silver 2": 5800, "Silver 3": 6600, "Silver 4": 7400, "Silver 5": 8200,
    "Gold 1": 9000, "Gold 2": 9800, "Gold 3": 10600, "Gold 4": 11400, "Gold 5": 12200,
    "Platinum 1": 13000, "Platinum 2": 14200, "Platinum 3": 15400, "Platinum 4": 16600, "Platinum 5": 17800,
    "Diamond 1": 19000, "Diamond 2": 20200, "Diamond 3": 21400, "Diamond 4": 22600, "Diamond 5": 23800,
    "Master": 25000
}

def clearOL(lp):
    try:
        numeric_part = re.sub(r'\D', '', lp)  # Remove all non-digit characters
        lp_value = int(numeric_part)
    except (ValueError, AttributeError):
        return None
    return lp_value

def get_rating_name(lp):
    lp_value = clearOL(lp)
    if lp_value is None:
        return "Unknown"

    # Find the highest rank that doesn't exceed lp_value
    for rank, threshold in sorted(rank_thresholds.items(), key=lambda x: x[1], reverse=True):
        if lp_value >= threshold:
            return rank

    return "Unknown"

bad_players = []

def scrape_player_data(driver, cfn):
    try:
        cfn_int = int(cfn)
        print(cfn_int)
    except ValueError:
        challonge_nickname = df_players.loc[df_players["CFN ЧИСЛОВОЙ Код игрока"] == cfn, "Participant Username"].values[0]
        bad_players.append((cfn, challonge_nickname))
        print(f'Not a cfn: {cfn}')
        return
    driver.get(f"https://www.streetfighter.com/6/buckler/ru/profile/{cfn}/play")
    try:
        driver.find_element(By.XPATH, "//*[contains(@class, 'not_exsist__')]")
        challonge_nickname = df_players.loc[df_players["CFN ЧИСЛОВОЙ Код игрока"] == cfn, "Participant Username"].values[0]
        bad_players.append((cfn, challonge_nickname))
        print("404 page detected")
        return
    except NoSuchElementException:
        pass

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
    max_lp = 0
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
            cleared_lp = clearOL(league_point_lp)
            if cleared_lp is not None:
                max_lp = max(max_lp, cleared_lp)
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
        matches=matches_data,
        max_lp=max_lp
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

#Deprecated
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

# ОСНОВНОЙ КОД ПРОГРАММЫ - Я ХЗ КАК MAIN В PYTHON сделать 

filename =  os.environ.get('PATH_TO_CSV')
df_players = pd.read_csv(filename)
players_cfn = df_players["CFN ЧИСЛОВОЙ Код игрока"].to_list()
if players_cfn:
    print("CFN успешно загружены:")
    print(players_cfn)
else:
    print("Список CFN пуст или произошла ошибка.")

min_matches, max_matches, max_rating = get_criteria_from_user()


# Set up the path to geckodriver if it's not in your system's PATH
geckodriver_path = os.environ.get('GECKODRIVER_PATH')  # Replace with the actual OS path
service = Service(geckodriver_path)

username = os.environ.get('CAPCOM_LOGIN')
password = os.environ.get('CAPCOM_PASSWORD')
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

df = pd.DataFrame(bad_players, columns=["Wrong CFN", "Bad player Nickname"])
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
    total_matches = sum(player.matches)

    # Check if the player should be highlighted
    max_lp = player.max_lp
    highlight = should_highlight_player(total_matches, max_lp, min_matches, max_matches, max_rating)
    challonge_nickname = df_players.loc[df_players["CFN ЧИСЛОВОЙ Код игрока"] == player.cfn, "Participant Username"].values[0]
    if challonge_nickname.lower() != player.name.lower():
        highlight = True

    num_phases = sum(len(character_data) for phase, character_data in player.phases.items())

    if highlight:
            for row in range(current_row, current_row + num_phases):
                highlight_row_red(worksheet, row, num_columns)

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

# Set column widths to auto-adjust based on maximum content length
for col in worksheet.columns:
    max_length = 0
    col_letter = get_column_letter(col[0].column)  # Get the column letter
    for cell in col:
        try:
            # Measure the length of each cell value
            if cell.value:
                max_length = max(max_length, len(str(cell.value)))
        except:
            pass
    # Adjust column width based on the maximum content length, with a buffer
    adjusted_width = (max_length + 2)  # Add some extra space for readability
    worksheet.column_dimensions[col_letter].width = adjusted_width

# Save the workbook after merging
workbook.save(excel_filename)

print(f"Data saved to {excel_filename} with merged cells for Player Names, CFNs, and Rating Names.")