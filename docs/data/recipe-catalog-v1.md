# PantryPilot recipe catalog v1

Status: **Owner-approved release**

- Author/owner: PantryPilot project owner
- Created: 2026-08-24
- Updated: 2026-08-25 (Task 5 owner-review fix round 1)
- Owner review: 2026-08-25
- Source: original PantryPilot-authored generic factual records; no external recipe material was copied
- Estimate method: calories, protein, and preparation time are rounded representative per-serving estimates for the named dish concepts. The model has no quantities, units, yields, or nutrition database.
- Catalog content version: 1
- Catalog manifest digest: `f811853765a0732ae34521e47c2f7e3c691f5cb00bfec4e138f9ce08a01c9f2c`
- Release state: this is the owner-approved version 1 release. The scoped data dedication is in [official-recipe-catalog-CC0-1.0.md](official-recipe-catalog-CC0-1.0.md).

Review tags are test and review evidence only; they are not `Recipe` fields.

## Official records

Band order is preparation / calories / protein / required-ingredient count.

| ID | Name | Ordered required ingredient IDs | Calories | Protein (g) | Prep (min) | Meal/category review tags | Tradition | Dietary | Derived bands |
| --- | --- | --- | ---: | ---: | ---: | --- | --- | --- | --- |
| `spinach-omelet` | Spinach Omelet | `eggs`, `spinach`, `olive-oil` | 410 | 28.0 | 15 | breakfast | American | vegetarian | `<=15` / `351-500` / `25-34.9` / `3-4` |
| `black-bean-tacos` | Black Bean Tacos | `black-beans`, `corn-tortillas`, `avocado`, `lime` | 520 | 19.0 | 25 | dinner; lunch/light-meal | Mexican | vegan | `16-30` / `501-650` / `15-24.9` / `3-4` |
| `peanut-noodles` | Peanut Noodles | `noodles`, `peanuts`, `soy-sauce` | 560 | 20.0 | 20 | dinner; lunch/light-meal | Southeast Asian | vegan | `16-30` / `501-650` / `15-24.9` / `3-4` |
| `lentil-soup` | Lentil Soup | `lentils`, `carrots`, `celery`, `vegetable-broth` | 360 | 22.0 | 45 | lunch/light-meal; soup/stew/salad | Mediterranean | vegan | `31-45` / `351-500` / `15-24.9` / `3-4` |
| `overnight-oats` | Overnight Oats | `oats`, `bananas`, `milk`, `peanuts`, `yogurt` | 340 | 14.0 | 10 | breakfast | American | vegetarian | `<=15` / `<=350` / `<15` / `5-6` |
| `avocado-egg-toast` | Avocado Egg Toast | `bread`, `eggs`, `avocado`, `spinach`, `olive-oil` | 350 | 18.0 | 10 | breakfast | American | vegetarian | `<=15` / `<=350` / `15-24.9` / `5-6` |
| `yogurt-oat-bowl` | Yogurt Oat Bowl | `yogurt`, `oats`, `bananas`, `peanuts`, `berries` | 380 | 14.0 | 5 | breakfast | American | vegetarian | `<=15` / `351-500` / `<15` / `5-6` |
| `tofu-rice-bowl` | Tofu Rice Bowl | `tofu`, `rice`, `broccoli`, `carrots`, `soy-sauce`, `garlic`, `ginger` | 510 | 26.0 | 35 | dinner; lunch/light-meal | East Asian | vegan | `31-45` / `501-650` / `25-34.9` / `7-8` |
| `tofu-vegetable-soup` | Tofu Vegetable Soup | `tofu`, `vegetable-broth`, `carrots`, `celery`, `spinach`, `soy-sauce`, `ginger` | 320 | 25.0 | 40 | lunch/light-meal; soup/stew/salad | East Asian | vegan | `31-45` / `<=350` / `25-34.9` / `7-8` |
| `beef-rice-bowl` | Beef Rice Bowl | `ground-beef`, `rice`, `broccoli`, `carrots`, `onion`, `garlic`, `soy-sauce`, `ginger` | 720 | 42.0 | 35 | dinner | East Asian | meat | `31-45` / `>650` / `>=35` / `7-8` |
| `chickpea-cucumber-salad` | Chickpea Cucumber Salad | `chickpeas`, `cucumbers`, `tomatoes`, `onion`, `lime`, `olive-oil`, `spinach` | 390 | 13.0 | 15 | lunch/light-meal; soup/stew/salad | Mediterranean | vegan | `<=15` / `351-500` / `<15` / `7-8` |
| `tomato-lentil-stew` | Tomato Lentil Stew | `lentils`, `tomatoes`, `onion`, `garlic`, `carrots`, `vegetable-broth`, `olive-oil`, `spinach` | 480 | 24.0 | 50 | dinner; soup/stew/salad | Mediterranean | vegan | `46-60` / `351-500` / `15-24.9` / `7-8` |
| `salmon-quinoa-salad` | Salmon Quinoa Salad | `salmon`, `quinoa`, `cucumbers`, `tomatoes`, `spinach`, `lime`, `olive-oil` | 570 | 38.0 | 30 | dinner; lunch/light-meal; soup/stew/salad | Mediterranean | fish | `16-30` / `501-650` / `>=35` / `7-8` |
| `chickpea-rice-bowl` | Chickpea Rice Bowl | `chickpeas`, `rice`, `cucumbers`, `tomatoes`, `onion`, `lime`, `yogurt`, `olive-oil` | 540 | 25.0 | 30 | dinner; lunch/light-meal | Middle Eastern | vegetarian | `16-30` / `501-650` / `25-34.9` / `7-8` |
| `lentil-cucumber-salad` | Lentil Cucumber Salad | `lentils`, `cucumbers`, `tomatoes`, `onion`, `lime`, `olive-oil` | 370 | 17.0 | 20 | lunch/light-meal; soup/stew/salad | Middle Eastern | vegan | `16-30` / `351-500` / `15-24.9` / `5-6` |
| `potato-chickpea-curry` | Potato Chickpea Curry | `potatoes`, `chickpeas`, `tomatoes`, `onion`, `garlic`, `spinach`, `coconut-milk`, `rice` | 680 | 18.0 | 55 | dinner | South Asian | vegan | `46-60` / `>650` / `15-24.9` / `7-8` |
| `coconut-lentil-curry` | Coconut Lentil Curry | `lentils`, `coconut-milk`, `tomatoes`, `onion`, `garlic`, `carrots`, `rice`, `spinach` | 620 | 24.0 | 50 | dinner | South Asian | vegan | `46-60` / `501-650` / `15-24.9` / `7-8` |
| `tuna-avocado-salad` | Tuna Avocado Salad | `tuna`, `avocado`, `cucumbers`, `tomatoes`, `lime`, `olive-oil`, `onion` | 430 | 35.0 | 15 | lunch/light-meal; soup/stew/salad | Latin American | fish | `<=15` / `351-500` / `>=35` / `7-8` |
| `black-bean-quinoa-salad` | Black Bean Quinoa Salad | `black-beans`, `quinoa`, `avocado`, `tomatoes`, `onion`, `lime`, `olive-oil` | 580 | 23.0 | 35 | lunch/light-meal; soup/stew/salad | Latin American | vegan | `31-45` / `501-650` / `15-24.9` / `7-8` |
| `chicken-tacos` | Chicken Tacos | `chicken`, `corn-tortillas`, `avocado`, `tomatoes`, `onion`, `lime`, `cabbage` | 610 | 40.0 | 30 | dinner | Mexican | poultry | `16-30` / `501-650` / `>=35` / `7-8` |
| `black-bean-rice-bowl` | Black Bean Rice Bowl | `black-beans`, `rice`, `avocado`, `tomatoes`, `onion`, `lime`, `cabbage`, `olive-oil` | 650 | 21.0 | 35 | dinner; lunch/light-meal | Mexican | vegan | `31-45` / `501-650` / `15-24.9` / `7-8` |
| `pasta-tomato-soup` | Pasta Tomato Soup | `pasta`, `tomatoes`, `onion`, `garlic`, `vegetable-broth`, `carrots`, `spinach`, `olive-oil` | 460 | 14.0 | 40 | lunch/light-meal; soup/stew/salad | Italian | vegan | `31-45` / `351-500` / `<15` / `7-8` |
| `chicken-pasta-bowl` | Chicken Pasta Bowl | `chicken`, `pasta`, `tomatoes`, `spinach`, `garlic`, `olive-oil`, `cheese` | 710 | 45.0 | 45 | dinner | Italian | poultry | `31-45` / `>650` / `>=35` / `7-8` |
| `coconut-chicken-stew` | Coconut Chicken Stew | `chicken`, `coconut-milk`, `potatoes`, `carrots`, `onion`, `garlic`, `lime` | 640 | 37.0 | 55 | dinner; soup/stew/salad | Southeast Asian | poultry | `46-60` / `501-650` / `>=35` / `7-8` |

## Aggregate coverage

- Identity: 24 records, 24 unique current IDs, the exact four Feature 003 IDs and facts preserved, zero retired IDs, zero duplicate retired IDs, and zero current/retired overlap.
- Registry: zero unknown relationship IDs, all 25 new canonical IDs used, and all 14 original registry records preserved byte-for-value.
- Meal/category tags: breakfast 4; lunch/light-meal 13; dinner 13; soup/stew/salad 10.
- Traditions: 9 represented. American 4; East Asian 3; Italian 2; Latin American 2; Mediterranean 4; Mexican 3; Middle Eastern 2; South Asian 2; Southeast Asian 2. Every represented tradition has 2–4 records; none exceeds 6.
- Dietary tags: vegan 13; vegetarian 5; fish 2; meat 1; poultry 3. Meat/fish-free total 18, including 13 vegan; poultry/fish/meat total 6.
- Preparation bands: `<=15` 6; `16-30` 6; `31-45` 8; `46-60` 4; beyond 60 zero.
- Calorie bands: `<=350` 3; `351-500` 8; `501-650` 10; `>650` 3.
- Protein bands: `<15` 4; `15-24.9` 10; `25-34.9` 4; `>=35` 6.
- Required-ingredient counts: minimum 3, maximum 8; `3-4` 4; `5-6` 4; `7-8` 16.
- Overlap: 24 of 24 recipes have a witness; 131 unordered pairs share at least two IDs; 13 canonical IDs occur in at least 4 but fewer than 24 recipes; duplicate unordered required-ingredient sets 0.
- Resolution negatives: all 6 targeted confusable inputs resolve as `unresolved`.

## At-least-one-overlap witnesses

The witness selected for each recipe has the largest shared-ID count, with recipe ID as the tie-breaker.

- `spinach-omelet` → `avocado-egg-toast`: `eggs`, `olive-oil`, `spinach`
- `black-bean-tacos` → `black-bean-quinoa-salad`: `avocado`, `black-beans`, `lime`
- `peanut-noodles` → `beef-rice-bowl`: `soy-sauce`
- `lentil-soup` → `tofu-vegetable-soup`: `carrots`, `celery`, `vegetable-broth`
- `overnight-oats` → `yogurt-oat-bowl`: `bananas`, `oats`, `peanuts`, `yogurt`
- `avocado-egg-toast` → `spinach-omelet`: `eggs`, `olive-oil`, `spinach`
- `yogurt-oat-bowl` → `overnight-oats`: `bananas`, `oats`, `peanuts`, `yogurt`
- `tofu-rice-bowl` → `beef-rice-bowl`: `broccoli`, `carrots`, `garlic`, `ginger`, `rice`, `soy-sauce`
- `tofu-vegetable-soup` → `tofu-rice-bowl`: `carrots`, `ginger`, `soy-sauce`, `tofu`
- `beef-rice-bowl` → `tofu-rice-bowl`: `broccoli`, `carrots`, `garlic`, `ginger`, `rice`, `soy-sauce`
- `chickpea-cucumber-salad` → `chickpea-rice-bowl`: `chickpeas`, `cucumbers`, `lime`, `olive-oil`, `onion`, `tomatoes`
- `tomato-lentil-stew` → `pasta-tomato-soup`: `carrots`, `garlic`, `olive-oil`, `onion`, `spinach`, `tomatoes`, `vegetable-broth`
- `salmon-quinoa-salad` → `chickpea-cucumber-salad`: `cucumbers`, `lime`, `olive-oil`, `spinach`, `tomatoes`
- `chickpea-rice-bowl` → `chickpea-cucumber-salad`: `chickpeas`, `cucumbers`, `lime`, `olive-oil`, `onion`, `tomatoes`
- `lentil-cucumber-salad` → `chickpea-cucumber-salad`: `cucumbers`, `lime`, `olive-oil`, `onion`, `tomatoes`
- `potato-chickpea-curry` → `coconut-lentil-curry`: `coconut-milk`, `garlic`, `onion`, `rice`, `spinach`, `tomatoes`
- `coconut-lentil-curry` → `potato-chickpea-curry`: `coconut-milk`, `garlic`, `onion`, `rice`, `spinach`, `tomatoes`
- `tuna-avocado-salad` → `black-bean-quinoa-salad`: `avocado`, `lime`, `olive-oil`, `onion`, `tomatoes`
- `black-bean-quinoa-salad` → `black-bean-rice-bowl`: `avocado`, `black-beans`, `lime`, `olive-oil`, `onion`, `tomatoes`
- `chicken-tacos` → `black-bean-rice-bowl`: `avocado`, `cabbage`, `lime`, `onion`, `tomatoes`
- `black-bean-rice-bowl` → `black-bean-quinoa-salad`: `avocado`, `black-beans`, `lime`, `olive-oil`, `onion`, `tomatoes`
- `pasta-tomato-soup` → `tomato-lentil-stew`: `carrots`, `garlic`, `olive-oil`, `onion`, `spinach`, `tomatoes`, `vegetable-broth`
- `chicken-pasta-bowl` → `pasta-tomato-soup`: `garlic`, `olive-oil`, `pasta`, `spinach`, `tomatoes`
- `coconut-chicken-stew` → `coconut-lentil-curry`: `carrots`, `coconut-milk`, `garlic`, `onion`

## Unordered pairs with at least two shared IDs

There are 131 qualifying pairs.

- `spinach-omelet` + `avocado-egg-toast`: `eggs`, `olive-oil`, `spinach`
- `spinach-omelet` + `chickpea-cucumber-salad`: `olive-oil`, `spinach`
- `spinach-omelet` + `tomato-lentil-stew`: `olive-oil`, `spinach`
- `spinach-omelet` + `salmon-quinoa-salad`: `olive-oil`, `spinach`
- `spinach-omelet` + `pasta-tomato-soup`: `olive-oil`, `spinach`
- `spinach-omelet` + `chicken-pasta-bowl`: `olive-oil`, `spinach`
- `black-bean-tacos` + `tuna-avocado-salad`: `avocado`, `lime`
- `black-bean-tacos` + `black-bean-quinoa-salad`: `avocado`, `black-beans`, `lime`
- `black-bean-tacos` + `chicken-tacos`: `avocado`, `corn-tortillas`, `lime`
- `black-bean-tacos` + `black-bean-rice-bowl`: `avocado`, `black-beans`, `lime`
- `lentil-soup` + `tofu-vegetable-soup`: `carrots`, `celery`, `vegetable-broth`
- `lentil-soup` + `tomato-lentil-stew`: `carrots`, `lentils`, `vegetable-broth`
- `lentil-soup` + `coconut-lentil-curry`: `carrots`, `lentils`
- `lentil-soup` + `pasta-tomato-soup`: `carrots`, `vegetable-broth`
- `overnight-oats` + `yogurt-oat-bowl`: `bananas`, `oats`, `peanuts`, `yogurt`
- `avocado-egg-toast` + `chickpea-cucumber-salad`: `olive-oil`, `spinach`
- `avocado-egg-toast` + `tomato-lentil-stew`: `olive-oil`, `spinach`
- `avocado-egg-toast` + `salmon-quinoa-salad`: `olive-oil`, `spinach`
- `avocado-egg-toast` + `tuna-avocado-salad`: `avocado`, `olive-oil`
- `avocado-egg-toast` + `black-bean-quinoa-salad`: `avocado`, `olive-oil`
- `avocado-egg-toast` + `black-bean-rice-bowl`: `avocado`, `olive-oil`
- `avocado-egg-toast` + `pasta-tomato-soup`: `olive-oil`, `spinach`
- `avocado-egg-toast` + `chicken-pasta-bowl`: `olive-oil`, `spinach`
- `tofu-rice-bowl` + `tofu-vegetable-soup`: `carrots`, `ginger`, `soy-sauce`, `tofu`
- `tofu-rice-bowl` + `beef-rice-bowl`: `broccoli`, `carrots`, `garlic`, `ginger`, `rice`, `soy-sauce`
- `tofu-rice-bowl` + `tomato-lentil-stew`: `carrots`, `garlic`
- `tofu-rice-bowl` + `potato-chickpea-curry`: `garlic`, `rice`
- `tofu-rice-bowl` + `coconut-lentil-curry`: `carrots`, `garlic`, `rice`
- `tofu-rice-bowl` + `pasta-tomato-soup`: `carrots`, `garlic`
- `tofu-rice-bowl` + `coconut-chicken-stew`: `carrots`, `garlic`
- `tofu-vegetable-soup` + `beef-rice-bowl`: `carrots`, `ginger`, `soy-sauce`
- `tofu-vegetable-soup` + `tomato-lentil-stew`: `carrots`, `spinach`, `vegetable-broth`
- `tofu-vegetable-soup` + `coconut-lentil-curry`: `carrots`, `spinach`
- `tofu-vegetable-soup` + `pasta-tomato-soup`: `carrots`, `spinach`, `vegetable-broth`
- `beef-rice-bowl` + `tomato-lentil-stew`: `carrots`, `garlic`, `onion`
- `beef-rice-bowl` + `chickpea-rice-bowl`: `onion`, `rice`
- `beef-rice-bowl` + `potato-chickpea-curry`: `garlic`, `onion`, `rice`
- `beef-rice-bowl` + `coconut-lentil-curry`: `carrots`, `garlic`, `onion`, `rice`
- `beef-rice-bowl` + `black-bean-rice-bowl`: `onion`, `rice`
- `beef-rice-bowl` + `pasta-tomato-soup`: `carrots`, `garlic`, `onion`
- `beef-rice-bowl` + `coconut-chicken-stew`: `carrots`, `garlic`, `onion`
- `chickpea-cucumber-salad` + `tomato-lentil-stew`: `olive-oil`, `onion`, `spinach`, `tomatoes`
- `chickpea-cucumber-salad` + `salmon-quinoa-salad`: `cucumbers`, `lime`, `olive-oil`, `spinach`, `tomatoes`
- `chickpea-cucumber-salad` + `chickpea-rice-bowl`: `chickpeas`, `cucumbers`, `lime`, `olive-oil`, `onion`, `tomatoes`
- `chickpea-cucumber-salad` + `lentil-cucumber-salad`: `cucumbers`, `lime`, `olive-oil`, `onion`, `tomatoes`
- `chickpea-cucumber-salad` + `potato-chickpea-curry`: `chickpeas`, `onion`, `spinach`, `tomatoes`
- `chickpea-cucumber-salad` + `coconut-lentil-curry`: `onion`, `spinach`, `tomatoes`
- `chickpea-cucumber-salad` + `tuna-avocado-salad`: `cucumbers`, `lime`, `olive-oil`, `onion`, `tomatoes`
- `chickpea-cucumber-salad` + `black-bean-quinoa-salad`: `lime`, `olive-oil`, `onion`, `tomatoes`
- `chickpea-cucumber-salad` + `chicken-tacos`: `lime`, `onion`, `tomatoes`
- `chickpea-cucumber-salad` + `black-bean-rice-bowl`: `lime`, `olive-oil`, `onion`, `tomatoes`
- `chickpea-cucumber-salad` + `pasta-tomato-soup`: `olive-oil`, `onion`, `spinach`, `tomatoes`
- `chickpea-cucumber-salad` + `chicken-pasta-bowl`: `olive-oil`, `spinach`, `tomatoes`
- `chickpea-cucumber-salad` + `coconut-chicken-stew`: `lime`, `onion`
- `tomato-lentil-stew` + `salmon-quinoa-salad`: `olive-oil`, `spinach`, `tomatoes`
- `tomato-lentil-stew` + `chickpea-rice-bowl`: `olive-oil`, `onion`, `tomatoes`
- `tomato-lentil-stew` + `lentil-cucumber-salad`: `lentils`, `olive-oil`, `onion`, `tomatoes`
- `tomato-lentil-stew` + `potato-chickpea-curry`: `garlic`, `onion`, `spinach`, `tomatoes`
- `tomato-lentil-stew` + `coconut-lentil-curry`: `carrots`, `garlic`, `lentils`, `onion`, `spinach`, `tomatoes`
- `tomato-lentil-stew` + `tuna-avocado-salad`: `olive-oil`, `onion`, `tomatoes`
- `tomato-lentil-stew` + `black-bean-quinoa-salad`: `olive-oil`, `onion`, `tomatoes`
- `tomato-lentil-stew` + `chicken-tacos`: `onion`, `tomatoes`
- `tomato-lentil-stew` + `black-bean-rice-bowl`: `olive-oil`, `onion`, `tomatoes`
- `tomato-lentil-stew` + `pasta-tomato-soup`: `carrots`, `garlic`, `olive-oil`, `onion`, `spinach`, `tomatoes`, `vegetable-broth`
- `tomato-lentil-stew` + `chicken-pasta-bowl`: `garlic`, `olive-oil`, `spinach`, `tomatoes`
- `tomato-lentil-stew` + `coconut-chicken-stew`: `carrots`, `garlic`, `onion`
- `salmon-quinoa-salad` + `chickpea-rice-bowl`: `cucumbers`, `lime`, `olive-oil`, `tomatoes`
- `salmon-quinoa-salad` + `lentil-cucumber-salad`: `cucumbers`, `lime`, `olive-oil`, `tomatoes`
- `salmon-quinoa-salad` + `potato-chickpea-curry`: `spinach`, `tomatoes`
- `salmon-quinoa-salad` + `coconut-lentil-curry`: `spinach`, `tomatoes`
- `salmon-quinoa-salad` + `tuna-avocado-salad`: `cucumbers`, `lime`, `olive-oil`, `tomatoes`
- `salmon-quinoa-salad` + `black-bean-quinoa-salad`: `lime`, `olive-oil`, `quinoa`, `tomatoes`
- `salmon-quinoa-salad` + `chicken-tacos`: `lime`, `tomatoes`
- `salmon-quinoa-salad` + `black-bean-rice-bowl`: `lime`, `olive-oil`, `tomatoes`
- `salmon-quinoa-salad` + `pasta-tomato-soup`: `olive-oil`, `spinach`, `tomatoes`
- `salmon-quinoa-salad` + `chicken-pasta-bowl`: `olive-oil`, `spinach`, `tomatoes`
- `chickpea-rice-bowl` + `lentil-cucumber-salad`: `cucumbers`, `lime`, `olive-oil`, `onion`, `tomatoes`
- `chickpea-rice-bowl` + `potato-chickpea-curry`: `chickpeas`, `onion`, `rice`, `tomatoes`
- `chickpea-rice-bowl` + `coconut-lentil-curry`: `onion`, `rice`, `tomatoes`
- `chickpea-rice-bowl` + `tuna-avocado-salad`: `cucumbers`, `lime`, `olive-oil`, `onion`, `tomatoes`
- `chickpea-rice-bowl` + `black-bean-quinoa-salad`: `lime`, `olive-oil`, `onion`, `tomatoes`
- `chickpea-rice-bowl` + `chicken-tacos`: `lime`, `onion`, `tomatoes`
- `chickpea-rice-bowl` + `black-bean-rice-bowl`: `lime`, `olive-oil`, `onion`, `rice`, `tomatoes`
- `chickpea-rice-bowl` + `pasta-tomato-soup`: `olive-oil`, `onion`, `tomatoes`
- `chickpea-rice-bowl` + `chicken-pasta-bowl`: `olive-oil`, `tomatoes`
- `chickpea-rice-bowl` + `coconut-chicken-stew`: `lime`, `onion`
- `lentil-cucumber-salad` + `potato-chickpea-curry`: `onion`, `tomatoes`
- `lentil-cucumber-salad` + `coconut-lentil-curry`: `lentils`, `onion`, `tomatoes`
- `lentil-cucumber-salad` + `tuna-avocado-salad`: `cucumbers`, `lime`, `olive-oil`, `onion`, `tomatoes`
- `lentil-cucumber-salad` + `black-bean-quinoa-salad`: `lime`, `olive-oil`, `onion`, `tomatoes`
- `lentil-cucumber-salad` + `chicken-tacos`: `lime`, `onion`, `tomatoes`
- `lentil-cucumber-salad` + `black-bean-rice-bowl`: `lime`, `olive-oil`, `onion`, `tomatoes`
- `lentil-cucumber-salad` + `pasta-tomato-soup`: `olive-oil`, `onion`, `tomatoes`
- `lentil-cucumber-salad` + `chicken-pasta-bowl`: `olive-oil`, `tomatoes`
- `lentil-cucumber-salad` + `coconut-chicken-stew`: `lime`, `onion`
- `potato-chickpea-curry` + `coconut-lentil-curry`: `coconut-milk`, `garlic`, `onion`, `rice`, `spinach`, `tomatoes`
- `potato-chickpea-curry` + `tuna-avocado-salad`: `onion`, `tomatoes`
- `potato-chickpea-curry` + `black-bean-quinoa-salad`: `onion`, `tomatoes`
- `potato-chickpea-curry` + `chicken-tacos`: `onion`, `tomatoes`
- `potato-chickpea-curry` + `black-bean-rice-bowl`: `onion`, `rice`, `tomatoes`
- `potato-chickpea-curry` + `pasta-tomato-soup`: `garlic`, `onion`, `spinach`, `tomatoes`
- `potato-chickpea-curry` + `chicken-pasta-bowl`: `garlic`, `spinach`, `tomatoes`
- `potato-chickpea-curry` + `coconut-chicken-stew`: `coconut-milk`, `garlic`, `onion`, `potatoes`
- `coconut-lentil-curry` + `tuna-avocado-salad`: `onion`, `tomatoes`
- `coconut-lentil-curry` + `black-bean-quinoa-salad`: `onion`, `tomatoes`
- `coconut-lentil-curry` + `chicken-tacos`: `onion`, `tomatoes`
- `coconut-lentil-curry` + `black-bean-rice-bowl`: `onion`, `rice`, `tomatoes`
- `coconut-lentil-curry` + `pasta-tomato-soup`: `carrots`, `garlic`, `onion`, `spinach`, `tomatoes`
- `coconut-lentil-curry` + `chicken-pasta-bowl`: `garlic`, `spinach`, `tomatoes`
- `coconut-lentil-curry` + `coconut-chicken-stew`: `carrots`, `coconut-milk`, `garlic`, `onion`
- `tuna-avocado-salad` + `black-bean-quinoa-salad`: `avocado`, `lime`, `olive-oil`, `onion`, `tomatoes`
- `tuna-avocado-salad` + `chicken-tacos`: `avocado`, `lime`, `onion`, `tomatoes`
- `tuna-avocado-salad` + `black-bean-rice-bowl`: `avocado`, `lime`, `olive-oil`, `onion`, `tomatoes`
- `tuna-avocado-salad` + `pasta-tomato-soup`: `olive-oil`, `onion`, `tomatoes`
- `tuna-avocado-salad` + `chicken-pasta-bowl`: `olive-oil`, `tomatoes`
- `tuna-avocado-salad` + `coconut-chicken-stew`: `lime`, `onion`
- `black-bean-quinoa-salad` + `chicken-tacos`: `avocado`, `lime`, `onion`, `tomatoes`
- `black-bean-quinoa-salad` + `black-bean-rice-bowl`: `avocado`, `black-beans`, `lime`, `olive-oil`, `onion`, `tomatoes`
- `black-bean-quinoa-salad` + `pasta-tomato-soup`: `olive-oil`, `onion`, `tomatoes`
- `black-bean-quinoa-salad` + `chicken-pasta-bowl`: `olive-oil`, `tomatoes`
- `black-bean-quinoa-salad` + `coconut-chicken-stew`: `lime`, `onion`
- `chicken-tacos` + `black-bean-rice-bowl`: `avocado`, `cabbage`, `lime`, `onion`, `tomatoes`
- `chicken-tacos` + `pasta-tomato-soup`: `onion`, `tomatoes`
- `chicken-tacos` + `chicken-pasta-bowl`: `chicken`, `tomatoes`
- `chicken-tacos` + `coconut-chicken-stew`: `chicken`, `lime`, `onion`
- `black-bean-rice-bowl` + `pasta-tomato-soup`: `olive-oil`, `onion`, `tomatoes`
- `black-bean-rice-bowl` + `chicken-pasta-bowl`: `olive-oil`, `tomatoes`
- `black-bean-rice-bowl` + `coconut-chicken-stew`: `lime`, `onion`
- `pasta-tomato-soup` + `chicken-pasta-bowl`: `garlic`, `olive-oil`, `pasta`, `spinach`, `tomatoes`
- `pasta-tomato-soup` + `coconut-chicken-stew`: `carrots`, `garlic`, `onion`
- `chicken-pasta-bowl` + `coconut-chicken-stew`: `chicken`, `garlic`

## Ingredients used by four or more recipes

All counts are below 24: `avocado` 6; `carrots` 8; `cucumbers` 5; `garlic` 8; `lentils` 4; `lime` 10; `olive-oil` 12; `onion` 13; `rice` 6; `soy-sauce` 4; `spinach` 10; `tomatoes` 13; `vegetable-broth` 4.

## New canonical ingredients

| ID | Canonical name | Approved aliases |
| --- | --- | --- |
| `oats` | oats | `oat` |
| `bananas` | bananas | `banana` |
| `berries` | berries | none |
| `milk` | milk | none |
| `yogurt` | yogurt | none |
| `bread` | bread | none |
| `tofu` | tofu | none |
| `rice` | rice | none |
| `broccoli` | broccoli | none |
| `garlic` | garlic | none |
| `ginger` | ginger | none |
| `onion` | onion | none |
| `ground-beef` | ground beef | none |
| `chickpeas` | chickpeas | `chickpea` |
| `cucumbers` | cucumbers | `cucumber` |
| `tomatoes` | tomatoes | `tomato` |
| `salmon` | salmon | none |
| `quinoa` | quinoa | none |
| `potatoes` | potatoes | `potato` |
| `coconut-milk` | coconut milk | none |
| `tuna` | tuna | none |
| `chicken` | chicken | none |
| `cabbage` | cabbage | none |
| `pasta` | pasta | none |
| `cheese` | cheese | none |

## Approved alias evidence

| Exact alias | Canonical ID | Positive reason | Exact confusable input that must remain unresolved |
| --- | --- | --- | --- |
| `oat` | `oats` | Common singular form naming the same whole ingredient. | `oat milk` |
| `banana` | `bananas` | Common singular form naming the same whole fruit. | `banana peppers` |
| `chickpea` | `chickpeas` | Common singular form naming the same whole legume. | `chickpea flour` |
| `cucumber` | `cucumbers` | Common singular form naming the same whole vegetable. | `cucumber water` |
| `tomato` | `tomatoes` | Common singular form naming the same whole ingredient. | `tomato paste` |
| `potato` | `potatoes` | Common singular form naming the same whole ingredient. | `sweet potato` |

The complete approved alias mapping is therefore `oat` → `oats`, `banana` → `bananas`, `chickpea` → `chickpeas`, `cucumber` → `cucumbers`, `tomato` → `tomatoes`, and `potato` → `potatoes`. No other new alias is approved.

## Targeted confusable negatives

Each exact input below is expected to resolve as `unresolved`: `oat milk`, `banana peppers`, `chickpea flour`, `cucumber water`, `tomato paste`, and `sweet potato`.

## Interpretation limits

All nutrition and preparation values are representative estimates. Meal, tradition, and dietary review tags are coverage evidence only; required ingredient lists are not exhaustive allergen declarations, and neither the facts nor tags are allergy, medical, or dietary-compliance guarantees.
