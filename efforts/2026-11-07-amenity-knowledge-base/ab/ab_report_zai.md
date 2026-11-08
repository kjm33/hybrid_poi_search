# A/B report: glm-5.3 vs glm-5.3-flash (50 stratified pages, seed 42)

## glm-5.3
- valid JSON: **100%**  | is_useful among valid: 82%
- avg latency: 45.5s  | avg tokens in/out: 1257/1494
- avg self_introduction length: 375 chars
- field fill: self_introduction=82%, intents=82%, keywords=86%, detailed_profile=86%, opening_hours=20%
- parse errors: none

## glm-5.3-flash
- valid JSON: **100%**  | is_useful among valid: 82%
- avg latency: 20.3s  | avg tokens in/out: 1257/1372
- avg self_introduction length: 359 chars
- field fill: self_introduction=82%, intents=82%, keywords=84%, detailed_profile=82%, opening_hours=24%
- parse errors: none

## Side-by-side samples

### acceleratorpreschool.com
**glm-5.3** (is_useful=True, page_type=business)

- intro: We are Accelerator Preschool, a childcare and early education provider offering preschool and pre-kindergarten programs in a safe, healthy and nurturing environment. We build a solid academic foundation for lifelong learning, helping children develop pre-reading, language, cognitive, social and physical skills during the critical first five years. We partner closely with parents and foster open communication and a sense of community. Classroom tours are available by appointment only, so call us at (408) 857-5585 to schedule a visit.
- intents: ['find a preschool near me', 'daycare and childcare for young children', 'pre-kindergarten enrollment', 'preschool with academic focus', 'schedule a preschool classroom tour', 'kindergarten readiness program']
- keywords: ['preschool', 'childcare', 'daycare', 'pre-k', 'pre-kindergarten', 'early childhood education', 'preschool enrollment', 'toddler program', 'kindergarten readiness', 'pre-reading skills', 'preschool tour', 'daycare center', 'nursery school']

**glm-5.3-flash** (is_useful=True, page_type=business)

- intro: We are Accelerator Preschool, a preschool education provider offering daycare, childcare, and pre-kindergarten programs for young children. Our mission is to provide a safe, healthy, and nurturing environment while building a solid academic foundation in pre-reading, language, cognitive, and social skills. We believe the first five years are critical to a child's future success and welcome strong parent involvement and open communication. Classroom tours are available by appointment, so please call us to learn more about our program.
- intents: ['find a preschool for my child', 'childcare or daycare for young children', 'pre-kindergarten readiness program', 'academic preschool focused on early literacy', 'schedule a preschool tour', 'preschool with strong parent communication']
- keywords: ['preschool', 'pre-kindergarten', 'pre-k', 'daycare', 'childcare', 'early childhood education', 'academic preschool', 'kindergarten readiness', 'pre-reading skills', 'nursery school', 'preschool enrollment', 'preschool tour', 'toddler learning program', 'safe nurturing preschool']

### anton.sbcusd.com
**glm-5.3** (is_useful=True, page_type=organization)

- intro: We are Antón Elementary School, a public elementary school in San Bernardino, California, serving local families as part of the San Bernardino City Unified School District. Our school community stays connected through district programs and events like the Child Development Program enrollment fair, parent advisory committee meetings, and English learner advisory meetings. We welcome families seeking a supportive public elementary education for their children.
- intents: ['public elementary school in San Bernardino', 'elementary school enrollment for my child', 'child development program enrollment', 'parent advisory committee meeting', 'English learner advisory committee meeting', 'school district news and events']
- keywords: ['anton elementary school', 'elementary school san bernardino', 'public elementary school', 'primary school', 'grade school', 'sbcusd', 'san bernardino city unified school district', 'child development program enrollment', 'parent advisory committee', 'english learner advisory committee']

**glm-5.3-flash** (is_useful=True, page_type=organization)

- intro: We are Antón Elementary School, a public elementary school in the San Bernardino City Unified School District. As part of SBCUSD, we connect our students and families with district news, parent advisory committees, and Board of Education meetings. Our school community serves elementary-age students in San Bernardino, California.
- intents: ['find an elementary school in San Bernardino', 'public elementary school enrollment', 'SBCUSD school information', 'district parent advisory committee meetings (AAPAC, DELAC)', 'school district board meetings']
- keywords: ['anton elementary school', 'elementary school san bernardino', 'sbcusd', 'san bernardino city unified school district', 'public elementary school', 'primary school san bernardino', 'san bernardino school district', 'elementary school near me']

### araujosmexicangrill.com
**glm-5.3** (is_useful=True, page_type=business)

- intro: We are Araujo's Mexican Grill, an authentic Mexican restaurant in San Jose serving mesquite-grilled carne asada, tripas, burritos, and street tacos with handmade tortillas fresh to order. What started as a food truck in 2005 has grown into three locations thanks to our fresh, flavorful food. Come enjoy our spacious dining room and salsa bar, or order online for takeout.
- intents: ['authentic Mexican food near me', 'street tacos', 'carne asada tacos', 'molcajete dinner', 'quick Mexican takeout', 'order Mexican food online', 'taqueria lunch', 'family dinner at a Mexican restaurant', 'salsa bar with chips']
- keywords: ['mexican restaurant san jose', 'taqueria san jose', 'authentic mexican food', 'carne asada', 'tripas', 'street tacos', 'tacos near me', 'burritos', 'molcajete', 'handmade tortillas', 'mesquite grilled steak', 'salsa bar', 'creamy green salsa', 'mexican food near me', 'order mexican food online', 'taco shop', 'mexican takeout']

**glm-5.3-flash** (is_useful=True, page_type=business)

- intro: We are Araujo's Mexican Grill, an authentic Mexican restaurant in San Jose serving tacos, burritos, carne asada and molcajete fresh daily since 2005. What started as a food truck has grown into three locations across the city. We grill our carne asada over real mesquite charcoal and press our tortillas by hand to order, and you can order online for pickup.
- intents: ['authentic Mexican tacos in San Jose', 'street tacos with salsa bar', 'carne asada grilled over charcoal', 'quick lunch with fast service', 'family dinner at a spacious clean restaurant', 'order Mexican food online', 'hearty seafood and meat molcajete', 'handmade tortillas made to order']
- keywords: ['taqueria', 'mexican restaurant san jose', 'authentic mexican food', 'street tacos', 'carne asada', 'burritos', 'tripas tacos', 'molcajete', 'shrimp molcajete', 'salsa bar', 'handmade tortillas', 'mesquite grilled carne asada', 'green salsa', 'tacos near me', 'order tacos online', 'food truck turned restaurant', 'mexican grill']

### bnaisrael.com
**glm-5.3** (is_useful=False, page_type=spam)

- intro: None
- intents: []
- keywords: []

**glm-5.3-flash** (is_useful=False, page_type=spam)

- intro: None
- intents: []
- keywords: []

### cabetos.com
**glm-5.3** (is_useful=True, page_type=business)

- intro: We are Cabetos Pops, a handmade organic ice cream shop on Adams Avenue in San Diego. Our mission is to bring back great tasting, all-natural ice cream pops made the old fashioned way. Build your own pop with your choice of flavors and toppings, or try one of our pop creations. We also offer catering, so let us host dessert at your next event!
- intents: ['family dessert outing', 'build your own ice cream pop', 'custom ice cream flavors and toppings', 'ice cream catering for events', 'kid-friendly treat shop', 'after-dinner ice cream']
- keywords: ['ice cream shop san diego', 'organic ice cream', 'handmade ice cream', 'ice cream pops', 'paletas', 'all natural ice cream', 'build your own ice cream', 'ice cream toppings', 'ice cream catering san diego', 'dessert catering', 'adams avenue ice cream', 'family ice cream shop', 'ice cream party', 'ice cream near me']

**glm-5.3-flash** (is_useful=True, page_type=business)

- intro: We are Cabetos Pops, a hand-made organic ice cream shop on Adams Avenue in San Diego. We bring back great tasting, all-natural ice cream pops made the old fashioned way, and you can build your own with your favorite flavors and toppings or try one of our pop creations. We also love hosting dessert at your next event through our catering service.
- intents: ['family-friendly dessert outing', 'organic ice cream treats', 'custom ice cream pops with toppings', 'dessert catering for events and parties', 'handmade ice cream shop near me', 'old fashioned ice cream pops']
- keywords: ['ice cream shop', 'organic ice cream', 'hand-made ice cream pops', 'ice cream pops', 'popsicles', 'san diego ice cream', 'adams avenue ice cream', 'build your own ice cream', 'ice cream toppings', 'all-natural ice cream', 'old fashioned ice cream', 'dessert catering', 'ice cream catering for events', 'family friendly dessert', 'custom ice cream flavors']
