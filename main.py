import sys
import bs4

from urllib.request import urlopen

def getHTML(url:str, refresh: bool = True) -> str:
	if not refresh:
		with open("testing", "r") as f:
			html: str = f.read()

	else:
		with urlopen(url) as response:
			html: str = response.read().decode('utf-8')
			with open("testing", "w") as f:
				f.write(html)
	
	return html

def extractData(html: str):
	soup = bs4.BeautifulSoup(html, "html.parser")
	relevantSection = soup.find("div", class_="main-content")
	mainContent: bs4.element.ResultSet = relevantSection.find("div", id="page-content").find_all(recursive=False)

	data: dict[str, str|int] = {}

	name = relevantSection.find("div", class_="page-title").find("span").string
	data["name"] = name

	for i in range(len(mainContent)):
		section: bs4.element.Tag = mainContent[i]

		# print(section)

		match i:
			case 0:
				if section.attrs["class"][0] != "content-separator":
					htmlErr(i)
				continue
			case 1:
				text: str = section.get_text()

				if text.count("Source") != 1:
					htmlErr(i)

				source = text.split(" ", 1)[1]
				data["source"] = source
			case 2:
				spellType: str = section.get_text()

				data["spellType"] = spellType

				# cantrips are written as <School> Cantrip
				# other spells are written as <Level> <School>
				if spellType.split(" ")[1].lower() == "cantrip":
					data["level"] = 0
				else:
					level: str = spellType[0]
					if not level.isnumeric():
						htmlErr(i)

					data["level"] = int(level)
			case 3:
				text: str = section.get_text()

				if text.lower().count("casting time") != 1:
					htmlErr(i)
				
				data["stats"] = text

	return data

def htmlErr(index: int):
	print(f"ERROR PARSING HTML (Unexepected layout) [{index}]")
	sys.exit(1)


def main():
	html = getHTML("https://dnd5e.wikidot.com/spell:thunderwave", False)
	data = extractData(html)

	print(data)

if __name__ == '__main__':
	main()
