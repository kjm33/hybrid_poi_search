# A/B report: glm-5.3-flash vs qwen3-30b-a3b-awq (50 stratified pages, seed 42)

## glm-5.3-flash
- valid JSON: **100%**  | is_useful among valid: 82%
- avg latency: 20.3s  | avg tokens in/out: 1257/1372
- avg self_introduction length: 359 chars
- field fill: self_introduction=82%, intents=82%, keywords=84%, detailed_profile=82%, opening_hours=24%
- parse errors: none

## qwen3-30b-a3b-awq
- valid JSON: **100%**  | is_useful among valid: 84%
- avg latency: 4.7s  | avg tokens in/out: 1284/448
- avg self_introduction length: 300 chars
- field fill: self_introduction=88%, intents=88%, keywords=88%, detailed_profile=86%, opening_hours=24%
- parse errors: none

## Side-by-side samples

### acceleratorpreschool.com
**glm-5.3-flash** (is_useful=True, page_type=business)

- intro: We are Accelerator Preschool, a preschool education provider offering daycare, childcare, and pre-kindergarten programs for young children. Our mission is to provide a safe, healthy, and nurturing environment while building a solid academic foundation in pre-reading, language, cognitive, and social skills. We believe the first five years are critical to a child's future success and welcome strong parent involvement and open communication. Classroom tours are available by appointment, so please call us to learn more about our program.
- intents: ['find a preschool for my child', 'childcare or daycare for young children', 'pre-kindergarten readiness program', 'academic preschool focused on early literacy', 'schedule a preschool tour', 'preschool with strong parent communication']
- keywords: ['preschool', 'pre-kindergarten', 'pre-k', 'daycare', 'childcare', 'early childhood education', 'academic preschool', 'kindergarten readiness', 'pre-reading skills', 'nursery school', 'preschool enrollment', 'preschool tour', 'toddler learning program', 'safe nurturing preschool']

**qwen3-30b-a3b-awq** (is_useful=True, page_type=business)

- intro: We are Accelerator Preschool, a dedicated early childhood education provider. We offer childcare, preschool, and pre-Kindergarten programs designed to nurture your child’s development in a safe, healthy, and supportive environment. Our mission is to build a strong academic foundation and promote lifelong learning through early skill development and individualized attention.
- intents: ['early childhood education', 'preschool for toddlers', 'pre-Kindergarten program', 'childcare for working parents', 'nurturing learning environment', 'parent-involved preschool']
- keywords: ['preschool', 'pre-kindergarten', 'childcare', 'early education', 'nursery school', 'toddler program', 'early learning center', 'preschool near me', 'daycare for toddlers']

### anton.sbcusd.com
**glm-5.3-flash** (is_useful=True, page_type=organization)

- intro: We are Antón Elementary School, a public elementary school in the San Bernardino City Unified School District. As part of SBCUSD, we connect our students and families with district news, parent advisory committees, and Board of Education meetings. Our school community serves elementary-age students in San Bernardino, California.
- intents: ['find an elementary school in San Bernardino', 'public elementary school enrollment', 'SBCUSD school information', 'district parent advisory committee meetings (AAPAC, DELAC)', 'school district board meetings']
- keywords: ['anton elementary school', 'elementary school san bernardino', 'sbcusd', 'san bernardino city unified school district', 'public elementary school', 'primary school san bernardino', 'san bernardino school district', 'elementary school near me']

**qwen3-30b-a3b-awq** (is_useful=True, page_type=business)

- intro: We are Antón Elementary School, part of the San Bernardino Unified School District. Our mission is to provide a safe, inclusive, and engaging learning environment where every student can thrive academically, socially, and emotionally. We offer a comprehensive curriculum focused on literacy, math, science, and social-emotional development, with strong support for English learners and families.
- intents: ['elementary school enrollment', 'parent-teacher meetings', 'school district events', 'family engagement activities', 'student academic support', 'English learner programs']
- keywords: ['anton elementary school', 'sbcusd', 'elementary school san bernardino', 'public school enrollment', 'parent advisory committee', 'english learner program', 'school district events']

### araujosmexicangrill.com
**glm-5.3-flash** (is_useful=True, page_type=business)

- intro: We are Araujo's Mexican Grill, an authentic Mexican restaurant in San Jose serving tacos, burritos, carne asada and molcajete fresh daily since 2005. What started as a food truck has grown into three locations across the city. We grill our carne asada over real mesquite charcoal and press our tortillas by hand to order, and you can order online for pickup.
- intents: ['authentic Mexican tacos in San Jose', 'street tacos with salsa bar', 'carne asada grilled over charcoal', 'quick lunch with fast service', 'family dinner at a spacious clean restaurant', 'order Mexican food online', 'hearty seafood and meat molcajete', 'handmade tortillas made to order']
- keywords: ['taqueria', 'mexican restaurant san jose', 'authentic mexican food', 'street tacos', 'carne asada', 'burritos', 'tripas tacos', 'molcajete', 'shrimp molcajete', 'salsa bar', 'handmade tortillas', 'mesquite grilled carne asada', 'green salsa', 'tacos near me', 'order tacos online', 'food truck turned restaurant', 'mexican grill']

**qwen3-30b-a3b-awq** (is_useful=True, page_type=business)

- intro: We are Araujo's Mexican Grill, a family-owned restaurant in San Jose, CA, serving authentic Mexican food since 2005. We grill our carne asada and tripas to order over real mesquite charcoal, use fresh, handmade tortillas, and prepare every dish with care. Whether you're craving street tacos, a hearty molcajete, or a satisfying burrito, we serve fresh, flavorful meals made with quality ingredients.
- intents: ['authentic Mexican food', 'fresh tacos', 'mesquite-grilled carne asada', 'handmade tortillas', 'family-friendly dinner', 'quick lunch', 'late-night snack', 'takeout', 'online ordering']
- keywords: ['mexican restaurant san jose', 'authentic tacos', 'carne asada tacos', 'mesquite grilled food', 'handmade tortillas', 'tacos to go', 'mexican food near me', 'best mexican food san jose', 'salsa bar', 'molcajete', 'taqueria', 'burritos to go']

### bnaisrael.com
**glm-5.3-flash** (is_useful=False, page_type=spam)

- intro: None
- intents: []
- keywords: []

**qwen3-30b-a3b-awq** (is_useful=False, page_type=spam)

- intro: We are KUDASAKTI168, a platform dedicated to fast and transparent saldo withdrawal. Our system ensures efficient, secure, and hassle-free fund transfers with clear verification steps and real-time tracking. Whether you're withdrawing from mobile or desktop, we make it simple and reliable.
- intents: ['withdraw funds quickly', 'check transaction status', 'verify withdrawal details', 'manage online balance']
- keywords: ['withdraw saldo', 'quick cash out', 'fast withdrawal', 'saldo transfer', 'online money withdrawal', 'secure cash out', 'transaction verification']

### cabetos.com
**glm-5.3-flash** (is_useful=True, page_type=business)

- intro: We are Cabetos Pops, a hand-made organic ice cream shop on Adams Avenue in San Diego. We bring back great tasting, all-natural ice cream pops made the old fashioned way, and you can build your own with your favorite flavors and toppings or try one of our pop creations. We also love hosting dessert at your next event through our catering service.
- intents: ['family-friendly dessert outing', 'organic ice cream treats', 'custom ice cream pops with toppings', 'dessert catering for events and parties', 'handmade ice cream shop near me', 'old fashioned ice cream pops']
- keywords: ['ice cream shop', 'organic ice cream', 'hand-made ice cream pops', 'ice cream pops', 'popsicles', 'san diego ice cream', 'adams avenue ice cream', 'build your own ice cream', 'ice cream toppings', 'all-natural ice cream', 'old fashioned ice cream', 'dessert catering', 'ice cream catering for events', 'family friendly dessert', 'custom ice cream flavors']

**qwen3-30b-a3b-awq** (is_useful=True, page_type=business)

- intro: We are Cabetos Pops, a hand-made organic ice cream shop in San Diego. We craft delicious, all-natural ice cream pops the old-fashioned way, using only quality ingredients. Whether you're building your own creation or trying one of our signature flavors, we bring back the joy of great-tasting frozen treats. Come visit us on Adams Avenue and enjoy a sweet, family-friendly experience.
- intents: ['family dessert', 'custom ice cream', 'event catering', 'organic frozen treats', 'weekend treat']
- keywords: ['organic ice cream', 'handmade pops', 'custom ice cream', 'family dessert', 'san diego ice cream', 'organic frozen treats', 'ice cream catering', 'build your own ice cream']
