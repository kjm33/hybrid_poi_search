# Cluster QA — bge-m3, UMAP(cosine→10d, n_neighbors=30) + HDBSCAN(euclidean), min_cluster_size=15

- vectors: 13199  clusters: 96  noise: 3553 (27%)

## Clusters by size

| cluster | n | top keywords | sample names |
|---|---|---|---|
| 0 | 874 | faith community, christian church, worship service, bible study, spiritual growth, christian fellowship | 11th Street Baptist Church; The Episcopal Church of Saint Andrew and Saint Charles; Anaheim First Church of the Nazarene; aaofcj.com |
| 70 | 637 | authentic italian food, pizza delivery, takeout pizza, vegan pizza, gluten free pizza, italian restaurant | 2051 Cucina Italiana; 786 Degrees Wood Fired Pizza Co; A16; A Bellagio Italian Restaurant |
| 54 | 610 | authentic mexican food, tacos, mexican food, burritos, catering mexican food, mexican restaurant | 5 Tacos & Beers; 701 Restaurant & Bar; 9 Julio Empanada Kitchen; Acapulco Restaurant and Cantina |
| 21 | 531 | family dentist, emergency dentist, cosmetic dentist, dental implants, general dentist, teeth whitening | 1AmazingSmile; Laser Eye Center of Silicon Valley; 395implants; Creekside Dental Care |
| 94 | 392 | specialty coffee, coffee shop, coffee subscription, local coffee shop, single origin coffee, sustainable coffee | 10 Speed Coffee; 11th Hour Coffee; 1428 HAIGHT Patio Café & Creperie; One Love Cafe |
| 37 | 318 | fresh sushi, sushi, sashimi, japanese restaurant, japanese food, sushi restaurant | 201 Kitchen SLO; Aikan Sushi; Aiko; Aka FujI Restaurant |
| 68 | 256 | early childhood education, nurturing preschool, preschool near me, play-based preschool, bilingual preschool, montessori preschool | 36th Street Early Education Center; ABC Learning Montessori; ABC Learning Preschool; Accelerator Preschool |
| 16 | 254 | community college california, associate degree, transfer to university, public university california, student support services, undergraduate programs | Asian American Activities Center; UC Irvine Office of Undergraduate Admissions; Advancing The University; AIMC |
| 40 | 237 | authentic chinese food, online chinese food order, handmade dumplings, takeout chinese food, chinese restaurant, chinese food delivery | 101 Noodle Express; AJ Chinese Express; Array36; Bafang Dumpling |
| 30 | 192 | authentic thai food, thai food near me, thai restaurant, thai food delivery, pad thai, thai food | 55 Thai Kitchen; Anajak Thai; Anchalee Thai Cuisine; Angkor Chef |
| 90 | 184 | cocktail bar san francisco, san francisco nightlife, craft cocktails san francisco, live music bar, private event bar, happy hour san francisco | 1015 Folsom; The 35er Bar; 620 Jones Bar and Restaurant; The Afterwork Bar |
| 77 | 181 | public high school california, college prep high school, high school education california, high school enrollment, high school events, student support | Acton-Agua Dulce Unified School District; adams.cnusd.k12.ca.us; Arcadia High School; Alisal High School |
| 88 | 173 | seafood restaurant, sustainable seafood, local seafood restaurant, local seafood, dinner with bay views, dungeness crab | Fish. / Bait; Ada's Fish House; Anchors Fish and Chips; Andria's Seafood Restaurant |
| 5 | 169 | pet dental care, vaccinations for pets, pet wellness exam, veterinarian near me, pet vaccinations, emergency vet | Four Paws Veterinary Clinic; Animal AM-Emergency Clinic of Pasadena; American Animal Hospital; ABC Pet Clinic |
| 63 | 166 | historic theater california, community theatre california, live performance venue, concert venue, historic movie theater, independent film screening | Adams Theater; All Out Comedy Theater; Marta Becket's Amargosa Opera House and Hotel; Arena Theater |
| 86 | 156 | local craft beer, craft beer bar, local brewery, craft beer, family friendly brewery, beer tasting | 47 Hills Brewing Company; Ale Arsenal; Lomita Alehouse; All Season Brewing |
| 74 | 151 | faith-based education, faith-based school, faith-based school california, faith-based education california, small class size school, catholic elementary school | Adventist Union School; Anthem Christian School; Arlington Christian School; Armenian Sisters' Academy |
| 12 | 127 | martial arts for kids, family martial arts, kids martial arts, discipline training, martial arts for beginners, adult martial arts | 101 Jiu Jitsu & Kickboxing; 7 Spears Martial Arts Poway; 805 Combat Sports; Aikido West |
| 60 | 123 | community health center, preventive care, behavioral health services, primary care, primary care clinic, chronic disease management | Adventist Health; All-Inclusive Community Health Center; All For Health, Health For All; Aria Community Health Center |
| 66 | 122 | mediterranean food, catering for events, hummus, shawarma, falafel, middle eastern food | Abu Omar Halal; Aegean; Aladdin Cafe; Maïsa |
| 83 | 118 | boba tea, bubble tea, milk tea, fresh boba, boba shop, premium tea | Sharetea; 3CAT Handcrafted Beverage; 805Boba; A. Boba Tea & Coffee |
| 49 | 111 | city council meeting, city council meetings, sacramento city services, 311 sacramento, city of milpitas, milpitas events | 511; City of Alameda; Albany; Alhambra City Council |
| 51 | 110 | developmental disabilities support, low income housing, family support services, affordable housing, low-income housing, senior housing | AbilityPath; Abode Services; Adjoin; Ala Costa Centers |
| 56 | 105 | authentic indian food, vegan indian food, indian food delivery, tandoori chicken, vegetarian indian food, spicy indian food | 5 Rivers Indian; Aappakadai Indian Chettinad; All India Cafe; Ambrosia India Bistro - Monterey Downtown |
| 73 | 104 | small class size school, college prep school, college prep high school, character education school, project-based learning school, college prep school california | Ace Charter School; ACE Charter High School; Adda Clevenger School; All Hallows Academy |
| 31 | 103 | pho, authentic pho, banh mi, vietnamese food, spring rolls, vietnamese sandwich | AL PHO; Anh Restaurant & Bar; BA LE Sandwich Shop; Banh Mi Ba Le |
| 93 | 95 | burger restaurant, milkshake, smash burger, veggie burger, crispy fries, chicken sandwich | Acme Burger; Adams Drive-In; Angelo's Burgers; Anny's Fine Burger |
| 58 | 94 | design hotel, luxury hotel, boutique hotel, romantic getaway california, historic hotel california, resort stay | Ace Hotel; Asha Urban Baths; Auberge Collection; Bigfoot Flat on Willow Creek |
| 50 | 91 | fire protection district, fire department, emergency medical services, fire safety, community services district, fire prevention | Alameda County Sheriff's Office; Alpine Fire Protection District; Anderson Valley Fire Department; Apple Valley Fire Protection District |

## Smallest clusters (QA: garbage?)

- cluster 79 (n=15): 21 Choices Frozen Yogurt; Go Greek Yogurt; Golden Spoon Frozen Yogurt; Loving Cup; Menchie's Frozen Yogurt
- cluster 42 (n=15): Alberhill Elementary School; Cottonwood Canyon Elementary School; Donald Graham Elementary School; Elsinore Elementary School; Earl Warren Elementary School
- cluster 46 (n=15): Superior Court of Alameda County; California Courts of Appeal; Calaveras County Superior Court; Superior Court of Inyo; Lassen County Superior Court
- cluster 52 (n=15): Allcove; Berkeley Youth Alternatives; Central Coast YMCA; Channel Islands YMCA; EBAYC
- cluster 32 (n=16): Bodega Community Association; Glendora Lodge #404; iooflodgedirectory.org; Lakehead Lions Club; Moose Lodge 1409
- cluster 41 (n=18): 5 POT; Big Way Hot Pot; Boiling Point; Yonny Mini Hot Pot; Happy Lamb Hot Pot
- cluster 57 (n=20): Aangan; Annapurna; Base Camp; Everest Restaurant; Everest Curry
- cluster 92 (n=20): Amangela's Sandwich and Bagel House; Bagel Exchange; Bagel Market; Bagel Me!; Bagel Nosh Deli
- cluster 29 (n=21): All City Tow Service; Auto Way Towing Service; BP TOWING; Brian's Towing Service; Dale's Transport Truck Wash
- cluster 62 (n=23): 9jaGrills; Abyssinia Ethiopian Restaurant; Addis; Barcote Ethiopian Restaurant; Blue Nile
- cluster 67 (n=23): Agape Grill; Barbayani Greek Taverna; Bravo Avo Greek and Mediterranean Cuisine; Dametra; George’s Greek Cafe
- cluster 36 (n=23): Beda's Biergarten; Der Biergarten; Biergarten; Das Bierhauz; Dutch Gardens
- cluster 20 (n=23): Berkeley Recycling Buyback Center; Big Bear Disposal; Circosta Iron & Metal Company; The Dutra Group; eWaste U.S.
- cluster 44 (n=23): Blue Ova Health & Acupuncture; California Center for Reproductive Medicine (CACRM); California Institute for Regenerative Medicine; California Cryobank; Dr. Nidhee Sachdev
- cluster 11 (n=24): Above All Aviation; ActivePILOT; Aero Academy; Aerodynamic Aviation; A-Hero Driving School

## Noise sample (25 random unclustered) — usually legit but unusual pages

- williamorr.llcsd.net — William Orr Elementary [school]
- lalascreamery.com — Lala's Creamery [restaurant]
- theramonaroom.com — The Ramona [bar]
- luckyboyburgers.com — Lucky Boy Burgers [restaurant]
- badashbakes.com — Bad Ash Bakes [bakery]
- gelato.love — Gelato Love [ice_cream]
- ojairotie.com — Ojai Rôtie [restaurant]
- nerdstreet.com — Nerd Street [college]
- lindygroove.com — LindyGroove [museum]
- trabocco.com — Trabocco [restaurant]
- waysidenoodles101.com — Wayside Noodles 101 [restaurant]
- hillwoodinvestmentproperties.com — Hillwood Investment Properties [beauty_salon]
- mvhs.fuhsd.org — Monta Vista High School [school]
- katskitchenberkeley.com — Kat's Kitchen [restaurant]
- rampsf.com — The Ramp [restaurant]
- evodyneacademy.com — Evodyne Robotics [school]
- oakobing.com — Oakobing [restaurant]
- cirlounge.com — CIR Lounge [restaurant]
- gymbarweho.com — GYM Bar WeHo [restaurant]
- citynationalgroveofanaheim.com — Grove of Anaheim [restaurant]
- thepeghouse.com — The Peg House [fuel]
- bushnell-lausd-ca.schoolloop.com — Bushnell Way Elementary School [school]
- rudfords.com — Rudford's Restaurant [restaurant]
- upcidersf.com — Upcider [restaurant]
- gage.riversideunified.org — Matthew Gage Middle School [school]
