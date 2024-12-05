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

	data: dict[str, str|int|list[str]] = {}

	name = relevantSection.find("div", class_="page-title").find("span").string
	data["name"] = name

	for i in range(len(mainContent)):
		section: bs4.element.Tag = mainContent[i]

		if "class" in section.attrs and section.attrs["class"][0] == "content-separator":
			continue

		text = section.get_text()

		match i:
			case 1:
				if text.count("Source") != 1:
					htmlErr(i)

				source = text.split(" ", 1)[1]
				data["source"] = source
				continue
			case 2:
				data["spellType"] = text

				# cantrips are written as <School> Cantrip
				# other spells are written as <Level> <School>
				if text.split(" ")[1].lower() == "cantrip":
					data["level"] = 0
				else:
					level: str = text[0]
					if not level.isnumeric():
						htmlErr(i)

					data["level"] = int(level)
				continue
			case 3:
				if text.lower().count("casting time") != 1:
					htmlErr(i)
				
				data["stats"] = text
				continue
		
		# last item (excluding separators) is always spell lists
		if i == len(mainContent)-2:
			if text.lower().count("spell lists") != 1:
				htmlErr(i)

			spellLists: list[str] = section.get_text().lower().split(".")[1].split(",")
			for i in range(len(spellLists)):
				spellLists[i] = spellLists[i].strip()
			
			data["spellLists"] = spellLists
			continue

		print(section.get_text())

	return data

def htmlErr(index: int):
	print(f"ERROR PARSING HTML (Unexepected layout) [{index}]")
	sys.exit(1)


def main():
	html = getHTML("https://dnd5e.wikidot.com/spell:thunderwave")
	data = extractData(html)

	print("")
	for i in data.keys():
		print(f"\033[94m{i}\033[0m: {data[i]}")

if __name__ == '__main__':
	main()
