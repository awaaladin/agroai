"""MockProvider: realistic canned answers (English and Pidgin) for demos and tests. No network, no cost."""
import hashlib

from app.ai.provider import ChatInput, DiagnoseInput, VisionProvider
from app.schemas.chat import ChatAnswer
from app.schemas.common import LOW_CONFIDENCE, Escalate, Language
from app.schemas.diagnose import Action, Alternative, Assessment, CropGuess, Diagnosis

# Each case: crop, crop confidence, problem confidence, serious (fast-spreading) flag, then per-language text.
# Chemicals are named by class only, never with doses (see the safety rules in the project brief).
CASES: dict[str, dict] = {
    "cassava_mosaic": {
        "crop": "cassava", "crop_conf": 0.95, "conf": 0.82, "serious": True,
        "alt": [("Cassava bacterial blight", 0.10), ("Nutrient shortage", 0.05)],
        "en": {
            "problem": "Cassava mosaic disease",
            "see": "The leaves are twisted and curled, with patches of pale yellow and green like a mosaic. The plant looks smaller than its neighbours.",
            "why": "Yellow and green patches with curled, distorted leaves is the typical sign of cassava mosaic, which is spread by whiteflies and by planting infected stems.",
            "change": "If the yellow patches follow the leaf veins in angles and the leaves are not curled, it may be a nutrient shortage instead. If you see many whiteflies, I become more sure.",
            "actions": [
                ("Pull out and burn or bury the worst infected plants so the disease does not spread.", "today", "Whiteflies carry the virus from sick plants to healthy ones."),
                ("Do not cut planting sticks from sick plants. Use stems from healthy plants only.", "this_week", "Infected stems pass the disease to the new crop."),
                ("Next season, plant mosaic-tolerant varieties. Ask your extension officer which ones are available near you.", "next_season", "Tolerant varieties give you a good harvest even when the disease is around."),
            ],
            "prevention": ["Use clean planting sticks from healthy plants.", "Plant tolerant varieties.", "Check your farm every week and remove sick plants early."],
            "questions": ["Are the new leaves also curled, or only the old ones?", "Do you see small white flies under the leaves?", "Are other cassava plants nearby also like this?"],
            "spoken": "Thank you for the photo. I can see twisted leaves with pale yellow and green patches. This looks like cassava mosaic disease, and I am fairly sure. It is spread by small white flies and by sick planting sticks. Please pull out the worst plants today and burn or bury them. Only plant sticks from healthy plants. Please check if the new leaves are curled too, and look for white flies under the leaves. Because this disease can spread fast, I also suggest you show this to your extension officer.",
            "escalate": "Cassava mosaic spreads fast between farms. An extension officer can confirm it and help with clean planting material.",
        },
        "pcm": {
            "problem": "Cassava mosaic sickness",
            "see": "The leaves don twist and curl, with pale yellow and green patches like mosaic. The plant small pass the ones wey dey near am.",
            "why": "Yellow and green patches with curl leaves na the correct sign of cassava mosaic. White flies and sick planting sticks dey carry am.",
            "change": "If the yellow patches just follow the leaf veins and the leaves no curl, e fit be say the soil no get enough food. If you see plenty white flies, I go sure pass.",
            "actions": [
                ("Comot the worst sick plants, burn or bury dem so the sickness no go spread.", "today", "White flies dey carry the sickness from sick plant go healthy one."),
                ("No cut planting sticks from sick plants. Use sticks from healthy plants only.", "this_week", "Sick sticks go give the new farm the same sickness."),
                ("Next season, plant cassava wey fit stand mosaic. Ask the extension officer which one dey near you.", "next_season", "That kain cassava go still give you good harvest even if the sickness dey around."),
            ],
            "prevention": ["Use clean planting sticks from healthy plants.", "Plant cassava wey fit stand mosaic.", "Waka round your farm every week and comot sick plants early."],
            "questions": ["The new leaves too dey curl, or na only the old ones?", "You see small white flies under the leaves?", "Other cassava near here dey like this too?"],
            "spoken": "Thank you for the photo. I see twist leaves with pale yellow and green patches. E look like cassava mosaic sickness, and I dey fairly sure. White flies and sick planting sticks dey carry am. Abeg comot the worst plants today and burn or bury dem. Use only sticks from healthy plants. Check if the new leaves too dey curl, and look under the leaves for white flies. Because this sickness fit spread fast, I suggest say make you show the extension officer.",
            "escalate": "Cassava mosaic dey spread fast. Extension officer fit confirm am and help you get clean planting sticks.",
        },
    },
    "yam_anthracnose": {
        "crop": "yam", "crop_conf": 0.9, "conf": 0.74, "serious": False,
        "alt": [("Leaf spot from poor drainage", 0.15), ("Insect damage", 0.07)],
        "en": {
            "problem": "Yam anthracnose",
            "see": "There are brown to black spots on the leaves, some with a yellow edge, and a few leaf tips look scorched.",
            "why": "Dark spots with yellow edges on yam leaves during wet weather match anthracnose, a fungus that thrives in warm, humid, crowded vines.",
            "change": "If the spots are tiny and only on leaves near the ground, it could be simple splash damage. If the spots are on the stems too, I am more sure.",
            "actions": [
                ("Remove and bury the badly spotted leaves. Do not leave them lying on the mound.", "today", "The fungus lives on old leaves and spreads in rain splashes."),
                ("Stake the vines so they climb up and get air, and weed around the mounds.", "this_week", "Air and sun dry the leaves and slow the fungus."),
                ("Next season, plant healthy seed yams and rotate with a different crop. Do not plant yam in the same spot again.", "next_season", "Rotation breaks the life cycle of the disease."),
            ],
            "prevention": ["Plant healthy seed yams.", "Stake vines for airflow.", "Rotate yam with other crops."],
            "questions": ["Did the spots start after heavy rain?", "Are the stems spotted too?", "Is the yam crowded or shaded by other plants?"],
            "spoken": "Thank you for the photo. I can see brown and black spots with yellow edges on the yam leaves. This looks like yam anthracnose. I am fairly sure, but not completely. Please remove the badly spotted leaves and bury them. Stake the vines so air can move through. Tell me, did the spots start after heavy rain, and are the stems spotted too?",
            "escalate": None,
        },
        "pcm": {
            "problem": "Yam anthracnose",
            "see": "Brown and black spots dey the leaves, some get yellow border, and some leaf tips like say fire burn dem.",
            "why": "Dark spots with yellow border for yam leaf for rainy time na anthracnose. The fungus like warm wet place wey vines dey crowd.",
            "change": "If the spots small and na only leaves wey near ground get am, e fit be only rain splash. If the stems get spots too, I go sure pass.",
            "actions": [
                ("Comot the leaves wey get plenty spots and bury dem. No leave dem for the mound.", "today", "The fungus dey live for old leaves and rain dey carry am go other leaves."),
                ("Stake the vines make dem climb up get air, and weed round the mounds.", "this_week", "Air and sun dey dry the leaves and slow the fungus."),
                ("Next season, plant healthy seed yam and change the crop. No plant yam for the same place again.", "next_season", "To change crop dey break the sickness."),
            ],
            "prevention": ["Plant healthy seed yam.", "Stake the vines make air waka.", "Change crop for the same land."],
            "questions": ["The spots start after heavy rain?", "The stems get spots too?", "Plants dey crowd or shade dey cover the yam?"],
            "spoken": "Thank you for the photo. I see brown and black spots with yellow border for the yam leaves. E look like yam anthracnose. I dey fairly sure but no be say I sure well well. Abeg comot the leaves wey get plenty spots and bury dem. Stake the vines make air fit waka. Tell me, the spots start after heavy rain, and the stems get spots too?",
            "escalate": None,
        },
    },
    "maize_fall_armyworm": {
        "crop": "maize", "crop_conf": 0.96, "conf": 0.85, "serious": True,
        "alt": [("Stem borer damage", 0.10), ("Hail or wind tear", 0.03)],
        "en": {
            "problem": "Fall armyworm in maize",
            "see": "There are ragged holes and long windows eaten in the young leaves, and fresh sawdust-like droppings in the whorl, the middle of the plant.",
            "why": "Fresh droppings in the whorl together with ragged holes in young leaves is the classic sign of fall armyworm caterpillars, which eat quickly.",
            "change": "If I cannot find any caterpillar in the whorl and the holes are neat and round, it may be another insect. Finding small caterpillars with an upside-down Y mark on the head would confirm it.",
            "actions": [
                ("Check 20 plants across the field in the early morning and look inside the whorl for caterpillars. Hand-pick and crush what you find.", "today", "Small numbers can be controlled by hand before they spread."),
                ("Put a pinch of dry sand or wood ash into the whorl of young plants.", "this_week", "It irritates the caterpillars and is cheap and local."),
                ("If many plants are damaged, ask your extension officer about an insecticide approved for maize. Follow the label, wear gloves, a mask and long clothes, and keep out of the field for the time on the label.", "this_week", "Chemicals are a last step, and the label and officer keep you and your family safe."),
            ],
            "prevention": ["Plant early and at the same time as your neighbours.", "Check the whorl every week.", "Rotate maize with a legume such as beans."],
            "questions": ["How many plants out of 20 have fresh damage?", "Did you find any caterpillars inside the whorl?", "How old is the maize, and how many days since it rained?"],
            "spoken": "Thank you for the photo. I see ragged holes in the young leaves and fresh droppings in the middle of the plant. This looks like fall armyworm, and I am quite sure. Early in the morning, check twenty plants and look inside the middle for caterpillars. Pick them out and crush them. A little dry sand or wood ash in the middle of young plants can help. If many plants are damaged, talk to your extension officer about a safe product, and always follow the label. How many plants out of twenty have fresh damage?",
            "escalate": "Fall armyworm spreads quickly across a field. An extension officer can advise on the right control for your stage of maize.",
        },
        "pcm": {
            "problem": "Fall armyworm for maize",
            "see": "Rough holes and long windows dey the young leaves, and fresh dust-like mess dey the middle of the plant.",
            "why": "Fresh mess for the middle with rough holes for young leaves na the correct sign of fall armyworm. The worms dey chop fast.",
            "change": "If I no see any worm for the middle and the holes neat and round, e fit be another insect. If you see small worms wey get upside-down Y mark for head, then e don clear.",
            "actions": [
                ("Early morning check 20 plants for different parts of the farm. Look inside the middle for worms. Pick dem and crush.", "today", "If dem still few, you fit control dem by hand before dem spread."),
                ("Put small dry sand or wood ash inside the middle of young plants.", "this_week", "E dey trouble the worms and e cheap, you fit find am for house."),
                ("If plenty plants don spoil, ask extension officer about insecticide wey dem approve for maize. Follow the label, wear gloves, mask and long cloth, and no enter the farm until the time wey label talk.", "this_week", "Chemical na last step. The label and officer go protect you and your family."),
            ],
            "prevention": ["Plant early and plant same time with your neighbours.", "Check the middle of the plants every week.", "Change maize with beans for the next planting."],
            "questions": ["Out of 20 plants, how many get fresh damage?", "You see any worm inside the middle?", "How old the maize be, and rain fall how many days ago?"],
            "spoken": "Thank you for the photo. I see rough holes for the young leaves and fresh mess for the middle of the plant. E look like fall armyworm, and I dey quite sure. Early morning, check twenty plants and look inside the middle for worms. Pick dem and crush. Small dry sand or wood ash for the middle of young plants fit help. If plenty plants don spoil, talk to your extension officer about safe product, and always follow the label. Out of twenty plants, how many get fresh damage?",
            "escalate": "Fall armyworm dey spread fast for farm. Extension officer fit tell you the correct way to control am for your maize stage.",
        },
    },
    "plantain_black_sigatoka": {
        "crop": "plantain", "crop_conf": 0.93, "conf": 0.70, "serious": False,
        "alt": [("Yellow sigatoka", 0.18), ("Natural leaf ageing", 0.08)],
        "en": {
            "problem": "Black sigatoka leaf disease",
            "see": "Dark brown streaks run along the leaf between the veins, and older leaves have large dead patches with a yellow edge.",
            "why": "Streaks that grow into dead patches, starting on older leaves, are typical of black sigatoka, a fungus that spreads in humid weather.",
            "change": "If only the very oldest leaves are affected and the newer leaves are clean, it may just be normal leaf ageing. If the streaks are on the youngest leaves, I am more sure.",
            "actions": [
                ("Cut off the leaves with more than a third dead and leave the cuttings away from the plants, or bury them.", "today", "Dead leaves release the spores that infect healthy leaves."),
                ("Remove extra suckers and weeds so the plantation has air and light.", "this_week", "Dry leaves slow the fungus."),
                ("Next season, ask your extension officer about tolerant plantain or banana varieties and correct spacing.", "next_season", "Tolerant varieties need much less work."),
            ],
            "prevention": ["Keep good spacing.", "Remove dead leaves regularly.", "Do not leave cut leaves lying in the plantation."],
            "questions": ["Are the youngest leaves also streaked?", "Is the whole plantation affected or only some stands?", "Is the plantation crowded with suckers?"],
            "spoken": "Thank you for the photo. I see dark brown streaks and dead patches on the older plantain leaves. This looks like black sigatoka. I am fairly sure, but not completely. Please cut off the leaves that are more than one third dead, and bury them. Remove extra suckers and weeds so that air can move. Tell me, are the youngest leaves also streaked, and is the whole plantation affected?",
            "escalate": None,
        },
        "pcm": {
            "problem": "Black sigatoka leaf sickness",
            "see": "Dark brown lines dey the leaf between the veins, and old leaves get big dead patches with yellow border.",
            "why": "Lines wey dey turn to dead patches, wey start from old leaves, na black sigatoka. Na fungus, e dey spread for wet weather.",
            "change": "If na only the oldest leaves get am and the new leaves clean, e fit be normal old age of leaf. If the youngest leaves get lines, I go sure pass.",
            "actions": [
                ("Cut the leaves wey dead pass one third and bury dem or put dem far from the plants.", "today", "Dead leaves dey release the spores wey dey infect healthy leaves."),
                ("Comot the extra suckers and weeds make air and light enter the farm.", "this_week", "Dry leaves dey slow the fungus."),
                ("Next season, ask extension officer for plantain or banana wey fit stand sigatoka, and correct spacing.", "next_season", "That kain plantain no dey give plenty work."),
            ],
            "prevention": ["Give the plants correct space.", "Dey cut dead leaves.", "No leave cut leaves for the plantation."],
            "questions": ["The youngest leaves get lines too?", "The whole plantation get am or na only some stands?", "Suckers dey crowd the plantation?"],
            "spoken": "Thank you for the photo. I see dark brown lines and dead patches for the old plantain leaves. E look like black sigatoka. I dey fairly sure but no be say I sure well well. Abeg cut the leaves wey dead pass one third and bury dem. Comot extra suckers and weeds make air waka. Tell me, the youngest leaves get lines too, and the whole plantation get am?",
            "escalate": None,
        },
    },
    "pepper_leaf_curl": {
        "crop": "pepper", "crop_conf": 0.88, "conf": 0.52, "serious": False,
        "alt": [("Mite damage", 0.22), ("Heat or water stress", 0.14), ("Nutrient shortage", 0.12)],
        "en": {
            "problem": "Pepper leaf curl, possibly a virus or mites",
            "see": "The leaves are curled upward and look a little thick and crinkled. Growth at the top seems stunted.",
            "why": "Upward curling with stunted tips can come from a virus carried by whiteflies, from tiny mites, or from stress, and the photo alone cannot separate them.",
            "change": "Tiny insects under the leaves would point to mites or whiteflies. Curling only on the hottest days that goes away at night would point to heat or water stress.",
            "actions": [
                ("Look under several leaves for tiny insects or webbing, and note what you find.", "today", "This is the clue that tells us which cause it is."),
                ("Remove and bury the worst curled plants if you see many whiteflies.", "this_week", "Sick plants can infect healthy ones."),
                ("Water in the early morning and mulch around the plants.", "this_week", "It helps if heat or water stress is part of the problem."),
            ],
            "prevention": ["Check under the leaves each week.", "Keep weeds down.", "Mulch the soil."],
            "questions": ["Do you see tiny insects or fine webs under the leaves?", "Does the curling get better in the evening?", "Are all the plants affected or only a few?"],
            "spoken": "Thank you for the photo. I can see curled leaves on your pepper. I am not sure what is causing it. It could be a virus, tiny mites, or heat. Please look under some leaves for tiny insects or fine webs and tell me what you see. Water early in the morning and put mulch on the soil. Because I am not sure, I suggest you show this to your extension officer.",
            "escalate": "I am not sure of the cause. An extension officer who can see the plants in person should confirm it.",
        },
        "pcm": {
            "problem": "Pepper leaf curl, e fit be virus or mites",
            "see": "The leaves curl go up and dem thick small and dey crinkle. The top of the plant no dey grow well.",
            "why": "Leaf wey curl go up with stunted top fit come from virus wey white flies carry, tiny mites, or stress. The photo alone no fit tell which one.",
            "change": "If you see tiny insects under the leaves, e fit be mites or white flies. If the curl dey only for hot afternoon and e dey better for night, e fit be heat or water stress.",
            "actions": [
                ("Look under some leaves for tiny insects or fine web and tell me wetin you see.", "today", "Na this one go show us the real cause."),
                ("Comot and bury the worst curl plants if you see plenty white flies.", "this_week", "Sick plants fit infect the healthy ones."),
                ("Water for early morning and cover the soil with dry grass.", "this_week", "E go help if heat or water stress dey part of the matter."),
            ],
            "prevention": ["Check under the leaves every week.", "Keep weeds down.", "Cover the soil with dry grass."],
            "questions": ["You see tiny insects or fine web under the leaves?", "The curl dey better for evening?", "All the plants get am or na only few?"],
            "spoken": "Thank you for the photo. I see curl leaves for your pepper. I no sure wetin dey cause am. E fit be virus, tiny mites, or heat. Abeg look under some leaves for tiny insects or fine web and tell me wetin you see. Water for early morning and cover the soil with dry grass. Because I no sure, I suggest say make you show the extension officer.",
            "escalate": "I no sure wetin cause am. Make extension officer wey fit see the plants confirm am.",
        },
    },
    "healthy": {
        "crop": "cassava", "crop_conf": 0.9, "conf": 0.9, "serious": False,
        "alt": [("Very early stage of a disease", 0.06)],
        "en": {
            "problem": "No problem seen, the plant looks healthy",
            "see": "The leaves are an even green with no spots, curling or holes, and the plant looks strong.",
            "why": "I do not see spots, twisting, holes or yellow patches, which are the signs I look for.",
            "change": "If you see spots, wilting or insects that the photo does not show, tell me and I will look again. A close photo of any odd leaf would help.",
            "actions": [
                ("Keep checking your plants every week, including under the leaves.", "this_week", "Catching a problem early makes it much easier to fix."),
                ("Keep the field weeded and the plants well spaced.", "this_week", "Air and light keep plants healthy."),
            ],
            "prevention": ["Check plants weekly.", "Keep weeds down.", "Use clean planting material."],
            "questions": ["Is anything about this plant worrying you that I cannot see in the photo?", "Are other plants on the farm the same?"],
            "spoken": "Thank you for the photo. Your plant looks healthy to me. The leaves are an even green, with no spots or holes. Keep checking your plants every week, even under the leaves. If something worries you that I cannot see, tell me and I will look again.",
            "escalate": None,
        },
        "pcm": {
            "problem": "I no see wahala, the plant dey healthy",
            "see": "The leaves green well, no spots, no curl, no holes, and the plant strong.",
            "why": "I no see spots, twist, holes or yellow patches, na dem I dey look for.",
            "change": "If you see spots, wilting or insects wey the photo no show, tell me and I go look again. Close photo of any strange leaf go help.",
            "actions": [
                ("Dey check your plants every week, even under the leaves.", "this_week", "If you catch wahala early, e easy to fix."),
                ("Keep the farm weeded and give the plants correct space.", "this_week", "Air and light dey keep plants healthy."),
            ],
            "prevention": ["Check plants every week.", "Keep weeds down.", "Use clean planting material."],
            "questions": ["Anything about this plant dey worry you wey I no fit see for photo?", "Other plants for the farm dey the same way?"],
            "spoken": "Thank you for the photo. Your plant dey healthy to me. The leaves green well, no spots or holes. Dey check your plants every week, even under the leaves. If anything dey worry you wey I no fit see, tell me and I go look again.",
            "escalate": None,
        },
    },
}

CROP_TO_CASE = {
    "cassava": "cassava_mosaic", "yam": "yam_anthracnose", "maize": "maize_fall_armyworm",
    "plantain": "plantain_black_sigatoka", "pepper": "pepper_leaf_curl",
}
HEALTHY_WORDS = ("healthy", "no problem", "looks fine", "e dey fine", "no wahala")


def pick_case(image: bytes, crop: str | None, symptoms: str | None) -> str:
    """Deterministic choice so demos and tests are repeatable."""
    if symptoms and any(w in symptoms.lower() for w in HEALTHY_WORDS):
        return "healthy"
    if crop in CROP_TO_CASE:
        return CROP_TO_CASE[crop]
    keys = list(CASES)
    return keys[int(hashlib.sha256(image).hexdigest(), 16) % len(keys)]


def build_diagnosis(case_key: str, language: Language) -> Diagnosis:
    case = CASES[case_key]
    text = case[language.value]
    low = case["conf"] < LOW_CONFIDENCE
    reason = text["escalate"]
    return Diagnosis(
        crop=CropGuess(name=case["crop"], confidence=case["crop_conf"]),
        assessment=Assessment(
            likely_problem=text["problem"], confidence=case["conf"],
            alternatives=[Alternative(name=n, confidence=c) for n, c in case["alt"]],
            what_i_see=text["see"], why_i_think_so=text["why"], what_could_change_my_mind=text["change"],
        ),
        actions=[Action(step=i, what=w, when=when, why=why) for i, (w, when, why) in enumerate(text["actions"], 1)],
        prevention=text["prevention"],
        farmer_questions=text["questions"],
        escalate=Escalate(recommended=bool(reason) or low or case["serious"], reason=reason),
        spoken_text=text["spoken"],
    )


# --- chat -------------------------------------------------------------------------------------

OUT_OF_SCOPE = ("doctor", "hospital", "sick child", "medicine for", "loan", "bank", "invest", "court", "lawyer", "police", "snake bite", "poison", "cow is", "goat is", "chicken is")
WEATHER_WORDS = ("spray", "plant", "harvest", "dry", "rain", "fertili", "fertiliz")

_DECLINE = {
    Language.en: "I can only help with farming questions. For health, money, legal or animal problems, please speak to a doctor, a bank, a lawyer or a vet. If someone is in danger, get help straight away.",
    Language.pcm: "I only dey help with farm matter. For health, money, law or animal wahala, abeg see doctor, bank, lawyer or vet. If person dey danger, go get help sharp sharp.",
}


class MockProvider(VisionProvider):
    name = "mock"

    async def diagnose(self, req: DiagnoseInput) -> Diagnosis:
        return build_diagnosis(pick_case(req.image, req.crop, req.symptoms_text), req.language)

    async def chat(self, req: ChatInput) -> ChatAnswer:
        pcm = req.language is Language.pcm
        msg = req.message.lower()

        if any(w in msg for w in OUT_OF_SCOPE):
            text = _DECLINE[req.language]
            return ChatAnswer(answer_text=text, spoken_text=text, confidence=1.0,
                              follow_up_suggestions=["Ask about my crop"])

        parts: list[str] = []
        confidence = 0.7
        escalate = Escalate()

        if req.diagnosis is not None:
            a = req.diagnosis.assessment
            confidence = a.confidence
            parts.append(f"About your {req.diagnosis.crop.name}: ")
            parts.append(a.likely_problem + ". ")
            if req.diagnosis.actions:
                parts.append(req.diagnosis.actions[0].what + " ")
            escalate = req.diagnosis.escalate
        else:
            parts.append(
                "Thank you for asking. Tell me which crop it is and what you see on the leaves, stems or roots, and I will help you think it through. "
                if not pcm else
                "Thank you for asking. Tell me which crop e be and wetin you see for the leaves, stems or roots, make we think am together. "
            )
            confidence = 0.5

        if req.weather and any(w in msg for w in WEATHER_WORDS):
            top = req.weather[0]
            parts.append(top.message_pcm if pcm else top.message)

        answer = "".join(parts).strip()
        followups = (["Wetin I fit do first?", "How I go stop am again?", "Show extension officer"] if pcm
                     else ["What should I do first?", "How can I stop it coming back?", "Share with an extension officer"])
        return ChatAnswer(answer_text=answer, spoken_text=answer, follow_up_suggestions=followups,
                          escalate=escalate, confidence=confidence)
