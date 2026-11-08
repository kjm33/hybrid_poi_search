# Stage-3 QA — profile-level tag verification

- shortlist: top 300 per tag, min sim 0.35
- 431 calls, 801,871 prompt tokens, 1,565,358 completion tokens

| tag | true | unsure | false | kept |
|---|---|---|---|---|
| family_friendly | 216 | 21 | 63 | 216 |
| business_friendly | 104 | 18 | 178 | 104 |
| work_friendly | 62 | 19 | 219 | 62 |
| pet_friendly | 141 | 3 | 156 | 141 |
| romantic | 88 | 59 | 153 | 88 |
| groups_events | 198 | 21 | 81 | 198 |
| late_night | 156 | 34 | 110 | 156 |
| accessible | 59 | 41 | 200 | 59 |
| casual | 221 | 45 | 34 | 221 |
| upscale | 71 | 34 | 195 | 71 |
| cozy | 120 | 61 | 119 | 120 |
| community_focused | 226 | 24 | 50 | 226 |
| lively | 147 | 37 | 104 | 147 |
| seniors | 149 | 6 | 145 | 149 |
| beginner_friendly | 107 | 31 | 162 | 107 |
| adults_only | 96 | 42 | 162 | 96 |
| lgbtq_friendly | 51 | 14 | 235 | 51 |

## Evidence spot-check (random 3 per tag)

### family_friendly
- **readysetgochildrenscenter.com**: “We are Ready Set Go Children's Center, a full-day childcare provider serving children from infancy through 8th grade.”
- **happababydaycare.com**: “We are Happa Baby, a childcare and early education center in Emeryville dedicated to providing a safe, respectful, and joyful environment for babies, toddlers, and preschoolers.”
- **36thsteec.lausd.org**: “We are 36th Street Early Education Center, a school dedicated to nurturing young minds in Los Angeles.”

### business_friendly
- **guildhouse.gg**: “Guildhouse is a 18,000-square-foot venue combining a lounge with local beer, craft cocktails, and gamer-focused food, a console and LAN gaming center with high-speed internet and latest tech, and flex”
- **club.clubcorp.com**: “Our clubs provide a welcoming environment for members to enjoy golf, dining, fitness, and networking opportunities.”
- **oasispartypalace.com**: “We are Oasis Palace, a premier event venue in Newark, CA, dedicated to hosting weddings, corporate events, birthdays, anniversaries, and cultural celebrations.”

### work_friendly
- **confidentialcoffee.com**: “The shop features complimentary Wi-Fi, numerous electrical outlets, a large community table for groups, and cozy seating with a selection of books from the community library.”
- **nextspace.us**: “We are NextSpace, a professional coworking and office space provider with 16 locations across California and Nevada.”
- **thelocal.cafe**: “We serve fresh breakfast and lunch options, a wide range of drinks, and offer a relaxed space to work, meet friends, or just unwind.”

### pet_friendly
- **the-barkmont.com**: “We offer premium daycare, boarding, grooming, and training services for dogs in Berkeley, Richmond, Oakland, and nearby areas.”
- **torreypinesvets.com**: “Our compassionate team of experienced veterinarians provides personalized, high-quality care for your pets, from routine wellness visits to advanced medical treatments.”
- **petcamp.com**: “We provide safe, fun, and enriching experiences for dogs and cats, with options for group play, individual enrichment, and specialized boarding.”

### romantic
- **20spot.com**: “We welcome guests for a quiet night out, a date, or a celebration with friends.”
- **terramialivermore.com**: “Whether you're planning a romantic dinner, birthday celebration, or business event, we offer a warm atmosphere and a menu crafted with care.”
- **ortosantamonica.com**: “We offer a romantic, elevated dining experience in a beautiful second-floor outdoor setting.”

### groups_events
- **rde.stanford.edu**: “We support the campus community by providing student housing, dining services, cafes, markets, the Stanford Guest House, catering, and conference services.”
- **pinotspalette.com**: “Our paint and sip events are perfect for birthdays, bachelorette parties, team building, or just a relaxing evening of art and wine.”
- **loftbarandbistro.com**: “We offer a vibrant mix of dining, nightlife, and event hosting with indoor and outdoor spaces, including a rooftop patio.”

### late_night
- **greatgreek.com**: “We are The Great Greek, a beloved Los Angeles restaurant that has been serving authentic Greek food, live music, and dancing since 1984.”
- **tinlizziesaloon.com**: “The venue hosts special events year-round, including performances by local music selectors and themed cocktail nights.”
- **sanfrancisco.wearespin.com**: “Late-night sessions run from 9PM on weeknights and 10PM on weekends, with half-off ping pong and special deals.”

### accessible
- **adaslodges.com**: “All locations offer accessible parking, including handicapped and guest spots, and are designed with senior-friendly mobility in mind.”
- **sothb.org**: “The church emphasizes inclusivity across age, culture, gender identity, sexual orientation, ability, and life stage.”
- **brookfieldhealthcare.net**: “We specialize in short-term rehabilitation and long-term care, helping patients regain strength and mobility.”

### casual
- **mamashelter.com**: “The properties feature rooftop lounges with cocktail menus, casual dining with homemade food, and a fun, welcoming atmosphere.”
- **confidentialcoffee.com**: “We serve thoughtfully crafted drinks and delicious pastries, and we welcome you to relax with a book from our community library, enjoy free Wi-Fi, and connect with others at our spacious communal tabl”
- **cafevida.net**: “We are Cafe Vida, a casual dining spot in Culver City focused on fresh, low-fat California and Latin dishes.”

### upscale
- **wolfgangpuck.com**: “His restaurants blend modern techniques with global influences, offering fine dining experiences across multiple continents.”
- **hawksrestaurant.com**: “We are Hawks Restaurant, a fine dining destination rooted in community and craftsmanship.”
- **auberge.com**: “The brand emphasizes unique, immersive experiences in nature and culture, with a focus on luxury accommodations, fine dining, wellness, and adventure travel.”

### cozy
- **rapportcoffeecs.com**: “Whether you're after clarity and purity or a cozy, customizable experience, we’ve got something for every palate.”
- **oslocoffee.co**: “Whether it's your morning coffee or a quiet moment to yourself, we hope every visit feels like home.”
- **simplywholesome.com**: “Whether you're here for a satisfying meal or a refreshing smoothie, we want you to feel at home.”

### community_focused
- **pegasusseniorliving.com**: “We create vibrant communities where residents continue to thrive through meaningful activities and compassionate care.”
- **salvationarmyusa.org**: “We are The Salvation Army USA, dedicated to serving communities across the nation.”
- **albanyca.org**: “We are the City of Albany, committed to serving our community by maintaining public spaces, improving infrastructure, and providing essential services.”

### lively
- **mattiesweho.com**: “Our vibrant atmosphere, great music, and welcoming staff make us the perfect spot for drinks, dancing, and dining.”
- **rockbarsf.com**: “We are Rock Bar, a lively spot in San Francisco where you can enjoy football on Sunday mornings starting at 10:00 am.”
- **19sportsbar.com**: “San Juan Hills Sports Bar & Grill offers a trendy, energetic environment perfect for watching sporting events.”

### seniors
- **swccsf.org**: “We are Southwest Community Corporation, serving seniors and individuals with disabilities in San Francisco's Lakeview, Oceanview, Merced Heights, and Ingleside neighborhoods.”
- **sanjosehc.com**: “seniors, post-surgical patients, individuals recovering from illness or injury”
- **morningstarseniorliving.com**: “We are MorningStar Senior Living, a community dedicated to helping seniors live with dignity, independence, and joy.”

### beginner_friendly
- **calvarybellflower.org**: “It offers introductory classes for new visitors, including Starting Point, Serve Point, and Share Point, to help people learn about Christianity and become members.”
- **ranchotelhorsecenter.com**: “We are Ranchotel Horse Center, a full-service equestrian facility dedicated to providing affordable boarding, lessons, and events for riders of all ages and skill levels.”
- **pkgla.com**: “Whether you're new to martial arts or looking to elevate your skills, our experienced coaches and supportive environment help you stay fit, confident, and focused.”

### adults_only
- **leftdoorsf.com**: “The venue is 21+ and encourages guests to dress to impress and limit phone use to preserve the ambiance.”
- **west.hollywood.trunksbar.com**: “Whether you're here for a quick drink, a game of pool, or to catch the game on one of our multiple TVs, you'll find a friendly crowd and fast service.”
- **rosamondseniorcenter.weebly.com**: “We are the Rosamond Senior Center, serving adults aged 50 and over in the Rosamond community.”

### lgbtq_friendly
- **hitopsbar.com**: “It is designed as a welcoming space for LGBTQ+ patrons and sports fans alike.”
- **glbthistory.org**: “We collect and preserve materials that reflect the diversity of LGBTQ history, culture, and arts.”
- **stocktonuu.org**: “You are welcome here whether you're single, married, LGBTQ+, or part of any other community.”

