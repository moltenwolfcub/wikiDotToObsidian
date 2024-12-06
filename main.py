import sys
import re
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

	for level in range(len(mainContent)):
		section: bs4.element.Tag = mainContent[level]

		if "class" in section.attrs and section.attrs["class"][0] == "content-separator":
			continue

		text: str = section.get_text()

		match level:
			case 1:
				if text.count("Source") != 1:
					htmlErr(level)

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
						htmlErr(level)

					data["level"] = int(level)
				continue
			case 3:
				if text.lower().count("casting time") != 1:
					htmlErr(level)
				
				data["stats"] = text
				continue
		
		# last item (excluding separators) is always spell lists
		if level == len(mainContent)-2:
			if text.lower().count("spell lists") != 1:
				htmlErr(level)

			spellLists: list[str] = section.get_text().lower().split(".")[1].split(",")
			for level in range(len(spellLists)):
				spellLists[level] = spellLists[level].strip()
			
			data["spellLists"] = spellLists
			continue

		if text.count("At Higher Levels.") == 1:
			# spellSlot/level -> damageDice
			damageDice: dict[int,str] = {}
			# for caption on higher level section
			uplevelType: str = ""
			uplevelDie: str = ""

			# Most non-cantrips with a higher level follow this structure
			nonCantrip: re.Match[str] | None = re.search(r"When you cast .*?(\d+d\d+).*?each.*?(\d)", text)
			# Most cantrips with a higher level follow this structure
			cantrip: re.Match[str] | None = re.search(r"damage increases by (\d+d\d+) when you reach", text)

			if nonCantrip != None:
				matchGroups = nonCantrip.groups()
				uplevelDie = matchGroups[0]
				startingLevel = int(matchGroups[1])

				diceInfo: list[str] = uplevelDie.split("d")

				for level in range(startingLevel, 10): # 1 more than 9 (the number of spells)
					above: int = level - startingLevel
					count: int = int(diceInfo[0]) * above

					modifiedDice: str = f"{count}d{diceInfo[1]}"
					damageDice[level] = modifiedDice

				uplevelType = "diceIncreasePerSlot"

			if cantrip != None:
				levels: list[tuple[str]] | None = re.findall(r"(\d+).{2} level \((\d+d\d+)\)", text)

				for match in levels:
					level = int(match[0])
					dice = match[1]
					damageDice[level] = dice

				uplevelDie = cantrip.groups()[0]
				uplevelType = "levelMilestone"


			data["higherLevels"] = damageDice
			data["uplevelType"] = uplevelType
			data["uplevelDie"] = uplevelDie
			continue

		print(section.get_text())

	return data

def htmlErr(index: int):
	print(f"ERROR PARSING HTML (Unexepected layout) [{index}]")
	sys.exit(1)


def main():
	html = getHTML("https://dnd5e.wikidot.com/spell:fire-bolt")
	data = extractData(html)

	print("")
	for i in data.keys():
		print(f"\033[94m{i}\033[0m: {data[i]}")

if __name__ == '__main__':
	main()
