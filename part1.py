from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service)

try:
    # Open the target website
    driver.get("https://aserg-ufmg.github.io/why-we-refactor/#/projects")

    # Wait for the table to load
    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "table")))  # Wait for the table to be present

    # Identify and retrieve all project links from the table
    project_elements = driver.find_elements(By.XPATH, "//table/tbody/tr/td[1]/a")  # Get all <a> tags in the first <td> of each row

    # Extract href attributes for each project link
    project_links = [element.get_attribute("href") for element in project_elements]

    # Write project links to a text file
    with open("project_links.txt", "w") as file:
        for link in project_links:
            file.write(link + "\n")

    print("Project links have been saved to project_links.txt")

finally:
    driver.quit()  # Close the browser
