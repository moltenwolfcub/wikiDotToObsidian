import sys
import re
import bs4
import os
import argparse

from urllib.request import urlopen
from urllib.error import HTTPError
from http.client import InvalidURL

def getSpellName() -> str:
	user = input("Spell Name >>> ")
	user = user.strip().lower() \
		.replace("(UA)","").strip() \
		.replace("'", "") \
		.replace(" ","-") \
		.replace("/","-") \
		.replace(":","-")
	return user

def getHTML(spell:str) -> str:
	url = f"https://dnd5e.wikidot.com/spell:{spell}"
	file = f"cache/{spell}"

	try:
		with open(file, "r") as f:
			return f.read()
	except FileNotFoundError:
		with urlopen(url) as response:
			html: str = response.read().decode('utf-8')

			with open(file, "w") as f:
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

		text: str = section.get_text()

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
			for j in range(len(spellLists)):
				spellLists[j] = spellLists[j].strip()
			
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
				startingSlot = int(matchGroups[1])

				diceInfo: list[str] = uplevelDie.split("d")

				for slot in range(startingSlot, 10): # 1 more than 9 (the number of spell slots)
					above: int = slot - startingSlot
					count: int = int(diceInfo[0]) * above

					modifiedDice: str = f"{count}d{diceInfo[1]}"
					damageDice[slot] = modifiedDice

				uplevelType = "diceIncreasePerSlot"

			if cantrip != None:
				levels: list[tuple[str]] | None = re.findall(r"(\d+).{2} level \((\d+d\d+)\)", text)

				for match in levels:
					level = int(match[0])
					dice = match[1]
					damageDice[level] = dice

				uplevelDie = cantrip.groups()[0]
				uplevelType = "levelMilestone"
			
			if cantrip == nonCantrip == None:
				print("No dice found for damage uplevel found so outputing text block")
				block = text.rstrip("At Higher Levels.").strip()

				uplevelDie = block
				uplevelType = "textBlock"
				damageDice[0] = "dummy"


			data["higherLevels"] = damageDice
			data["uplevelType"] = uplevelType
			data["uplevelDie"] = uplevelDie
			continue

		if data.get("description") is None:
			data["description"] = []
		data["description"].append(text)

		if m := re.findall(r"(\d*d\d+)", text):
			if data.get("baseDie") is not None:
				htmlErr(i, "More than one dice in description")
			
			if len(m) > 1:
				htmlErr(i, "More than one dice in description")

			data["baseDie"] = m[0] 

	return data

def htmlErr(index: int, errType: str = "Unexepected layout"):
	print(f"ERROR PARSING HTML ({errType}) [{index}]")
	sys.exit(1)

def markdownErr(errtype: str):
	print(f"ERROR BUILDING MARKDOWN ({errtype}))")
	sys.exit(1)

def buildMarkdown(data: dict) -> str:
	markdown = ""

	if source := data.get("source"):
		markdown += f"**Source:** {source}\n"

	if spellType := data.get("spellType"):
		markdown += f"_{spellType}_\n"
	
	if markdown:
		markdown += "\n"
	
	if stats := data.get("stats"):
		stats: str

		for stat in stats.split("\n"):
			parts = stat.split(": ")

			markdown += f"**{parts[0]}:** {parts[1]}\n"
		
		markdown += "\n"
	
	if desc := data.get("description"):
		desc: list[str]

		for d in desc:
			d = re.sub(r"(\d*d\d+)", r"`dice:\g<1>`", d)
			d = re.sub(r"(\w+ spell attack)", r"**\g<1>**", d)
			d = re.sub(r"((?:strength|dexterity|constitution|intelligence|wisdom|charisma) saving throw)", r"**\g<1>**", d, flags=re.IGNORECASE)
			d = re.sub(r"(\d+ feet)", r"**\g<1>**", d)

			d = re.sub(r"((?:strength|dexterity|constitution|intelligence|wisdom|charisma)(?: \(.+\))? check)", r"**\g<1>**", d, flags=re.IGNORECASE)
			d = re.sub(r"(spell save DC)", r"**\g<1>**", d)

			markdown += d+"\n\n"
	
	if higherLevels := data.get("higherLevels"):
		higherLevels: dict[int,str]
		
		markdown += "#### Higher Levels\n"

		match data.get("uplevelType"):
			case "levelMilestone":
				markdown += f"This spell's damage increases by `dice:{data["uplevelDie"]}` at each of these milestones\n\n"

				tableSource = higherLevels.copy()

				if (baseDie := data.get("baseDie")) is not None:
					tableSource[1] = baseDie
				
				tableSource = {k: f"`dice:{tableSource[k]}`" for k in sorted(tableSource)}

				markdown += formTable(tableSource, "Level", "Damage Dice")
			case "diceIncreasePerSlot":
				markdown += f"This spell's damage increases by `dice:{data["uplevelDie"]}` when cast with a higher slot\n\n"

				tableSource = higherLevels.copy()
				if (baseDie := data.get("baseDie")) is None:
					markdownErr("No base dice found")
				else:
					baseDie: str

					for key in tableSource:
						dice = tableSource[key].split("d")
						base = baseDie.split("d")

						if dice[1] != base[1]:
							markdownErr(f"Base die and increase dice aren't the same dice type (at level {key})")

						tableSource[key] = f"`dice:{int(dice[0]) + int(base[0])}d{dice[1]}`"

				markdown += formTable(tableSource, "Slot", "Damage Dice")

			case "textBlock":
				markdown += f"{data["uplevelDie"]}\n\n"

			case _:
				markdownErr("Unknown uplevel spell type")
				sys.exit(1)
	
	if spellLists := data.get("spellLists"):
		markdown += "#### Spell lists\n"

		for spellList in spellLists:
			spellList: str

			markdown += f"- {spellList.title()}\n"

	return markdown

def formTable(mapping: dict, keyHeading: str, valueHeading: str) -> str:
	table = ""

	leftMax = len(keyHeading)
	rightMax = len(valueHeading)

	for k in mapping.keys():
		left = len(str(k))
		right = len(str(mapping[k]))

		leftMax = left if left > leftMax else leftMax
		rightMax = right if right > rightMax else rightMax
	
	def padEntry(key: str, value: str) -> str:
		return f"| {key}{" "*(leftMax-len(key))} | {value}{" "*(rightMax-len(value))} |\n"

	table += padEntry(keyHeading, valueHeading)
	table += f"| {"-"*leftMax} | {"-"*rightMax} |\n"

	for k in mapping.keys():
		left = str(k)
		right = str(mapping[k])

		table += padEntry(left, right)

	return table


def writeToFile(md: str, name: str, level: int, dir: str) -> None:
	subFolder = ""
	if level == 0:
		subFolder = "Cantrips"
	else:
		subFolder = f"Level {level}"

	name = name.replace(":", " -")
	name = name.replace("/", "-")

	completeDir = f"{dir}{subFolder}"
	if not os.path.isdir(completeDir):
		os.mkdir(completeDir)

	with open(f"{completeDir}/{name}.md", "w") as f:
		f.write(md)

def main(dir: str = "out/"):
	while True:
		try:
			spell = getSpellName()
			if spell == "":
				print("Please enter a spell name or q to exit")
				continue
			elif spell == "q":
				sys.exit()

			html = getHTML(spell)
		except HTTPError:
			print("Couldn't find that spell")
		except InvalidURL:
			print("spell contains invalid characters. Please try again")
		else:
			break

	data = extractData(html)
	md = buildMarkdown(data)
	writeToFile(md, data["name"], data["level"], dir)

	# for i in data.keys():
	# 	print(f"\033[94m{i}\033[0m: {data[i]}")

	# print("\n"+md)

if __name__ == '__main__':
	parser = argparse.ArgumentParser(
		prog= "Wikidot to Obsidian",
		description= "Generates Obsidian markdown files from DnD Wikidot"
	)
	parser.add_argument("directory")
	args = parser.parse_args()
	
	while True:
		main(args.directory)

		if input("[Q] to exit. Anything else to go again.").lower().strip() == "q":
			break
