import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import NoSuchElementException
from dataclasses import dataclass

from helpers.clear_OL import clear_OL

@dataclass
class Player:
    name: str
    cfn: str
    phases: dict
    matches: list
    max_lp: int
    played_time: list

def scrape_player_data(driver, cfn, df_players, bad_players):
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
            cleared_lp = clear_OL(league_point_lp)
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


    profile_button_xpath = '/html/body/div[1]/div/aside[2]/div/ul/li[1]'
    profile_button = WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.XPATH, profile_button_xpath))
    )
    profile_button.click()

    time_section_xpath = '/html/body/div[1]/div/article[3]/div/div/div[2]/article[1]/section[3]'
    time_section = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, time_section_xpath))
    )
    time_elements = time_section.find_elements(By.TAG_NAME, "dl")

    played_time_list = []

    for time_element in time_elements:
        played_time = time_element.find_elements(By.TAG_NAME, "dd")[0].text
        print(played_time)
        played_time_list.append(played_time)

    #Возвращаем структуру
    return Player(
        name=player_name,
        cfn=cfn,
        phases=phases,
        matches=matches_data,
        max_lp=max_lp,
        played_time=played_time_list
    )
