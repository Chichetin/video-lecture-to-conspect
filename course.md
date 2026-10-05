# Контекст курса и словарь (VK Education · Рекомендательные системы)

Используй при правке терминов (шаг 4), в заданиях субагентам и в YAML конспекта. Пополняй этот файл после каждой лекции новыми подтверждёнными терминами и искажениями.

**Курс.** VK Education, «Рекомендательные системы», 25.09.2026 – 04.12.2026: 10 лекций (пятницы), 7 семинаров (субботы), 4 рубежных контроля (РК = «промежуточный тест», 7 баллов), 3 ДЗ (15 баллов, сдаются на **AllCups** — Python-файл по шаблону, автопроверка), итоговый тест = «экзамен» (23 балла), обратная связь (4 балла).
Преподаватели: Олег Сапрыкин (лектор 1-й лекции, ведущий разработчик / ML-инженер VK, рекомендации VK Клипов и Одноклассников), Максим Утушкин, Александр Андреев, Михаил Маслов, Нелли Перфильева.
Программа: 1 — Введение в рекомендательные системы; 2 — Ранжирование и метрики качества; 3 — Признаки и классические рекомендательные модели; 4 — Двухбашенные модели; 5 — Sequential Recommendation; 6 — Нейросетевая кандидатогенерация; 7 — Нейросетевое ранжирование; 8 — Графовые нейронные сети; 9 — LLM × RecSys; 10 — Перспективы рекомендательных систем.
Продукты VK, которые упоминаются как примеры: VK Клипы, VK Видео, VK Музыка, VK Знакомства, Одноклассники, ВКонтакте.

**Написание терминов** (как в слайдах курса): RecSys, айтем (item), юзер/пользователь (user), top-N, кандидатогенерация, ранжирование, двухбашенные модели, explicit / implicit feedback, коллаборативная фильтрация, content-based filtering, memory-based / model-based, SVD, ALS (Alternating Least Squares), Factorization Machines (факторизационные машины), MovieLens, Netflix Prize, ACM RecSys, Wide & Deep, Neural FM, DeepFM, SASRec, BERT4Rec, EASE, Mult-VAE, causal inference, XAI, LLM, AutoML, feed-forward, эмбеддинги, k-means, survival analysis, A/B-тест, Challenges / Data / Models / Evaluation, bias: user-selection, exposure, conformity, position, inductive, popularity; fairness / unfairness, filter bubble (информационный пузырь), exploration, холодный старт, Online Modules, Recommender Systems Handbook, Precedence Research.

**Типичные искажения SpeechKit** (подтверждены в лекции 1 — можно применять как `уверенно`):

| Звучит в расшифровке | Правильно |
|---|---|
| атом, атомы, атомов, айтом, айтен, Айден, «а этом» (отдельно) | айтем, айтемы, айтемов… |
| рексис, рексиса, рексисы, элексис | RecSys |
| Эмэль | ML |
| Автоэмэль, «авто, и Мейли» | AutoML |
| Олкапс, Олкапсу, Калксии, Капси | AllCups |
| зарубежный контроль | рубежный контроль |
| корпоративная фильтрация | коллаборативная фильтрация |
| СВД / Алс / ЛЛМ, «ала Лемок» | SVD / ALS / LLM |
| интернет лист склер | Alternating Least Squares |
| катаризационные, вктрадиционные (машины) | факторизационные |
| фитфорвард | feed-forward |
| ТОН / топ н / топ эн / стоп н | top-N |
| двубашенные | двухбашенные |
| секвеншион | Sequential |
| эмбидинги | эмбеддинги |
| камин с | k-means |
| Айтен Диб | Wide & Deep |
| Нейрол, ФМ / ДИП ФМ, Зип ФМ | Neural FM / DeepFM |
| САС рек Берт Фориак / Берт / Мультвае | SASRec, BERT4Rec / BERT / Mult-VAE |
| Муви Лэнс | MovieLens |
| Эй 7 Лексис | ACM RecSys |
| информейшн на ТПстре / Нет Ресепшенс | Information Tapestry / Net Perceptions |
| Мемори Бейст / модель Бейст | memory-based / model-based |
| Сурвайвал анализис | survival analysis |
| Челленджес, Дейта, модели и эволюишн | Challenges, Data, Models и Evaluation |
| Юзер Селекшн (Бейс) / Икс тоже Байз, эксплужа Байз, эксплорер Байерс / Конформите сон / Апатишин Байз / индактив Байз / популярити байз | user-selection bias / exposure bias / conformity bias / position bias / inductive bias / popularity bias |
| от Фернес / анфернесс, Анфайрнас / экспорейшн / Байксы | fairness / unfairness / exploration / bias'ы |
| Имплесит | implicit |
| рекомендор систем Хэнкбук | Recommender Systems Handbook |
| Пресидион Срисевич | Precedence Research |
| клоды, Клодом / чат джипити | Claude / ChatGPT |
| Икс 5 / экспрессикора, фуразон | X5 / X5, Carrefour, Ozon |
| бетона (в контексте языка программирования) | Python |

**Трактовки по смыслу, не подтверждённые на слух** (применять только как `по смыслу` и перечислять в отчёте): «Модэл» → Moodle (платформа тестов РК); «вкусов на бока Юкаешь» → «курсов в VK Education»; «на лука» → «на AllCups»; «мальчики» → «ML-щики»; «медикал Кридзмент» → medical treatment; «Яндекса Тиви» → Яндекс ТВ.

**Лекция 2 (Максим Утушкин, «Ранжирование и метрики качества»).** Термины: ранкер, реранкер, RAG, retrieval, асессоры / асессорская разметка, краудсорсинг, онлайн-сигналы, guardrail-метрики, сессия, DCG / IDCG / NDCG (discounted cumulative gain), pointwise / pairwise / listwise (поточечный / попарный / списочный), MSE, MAE, LogLoss, hinge, PRank («Pranking with Ranking»), CORAL, CORN, RankNet, LambdaRank, LambdaLoss, EM-алгоритм, лемма Пуанкаре, модель Плакетта–Люса, ListNet, ListMLE, SGD, метод Ньютона, гессиан, XGBoost, CatBoost, PairLogit / PairLogitPairwise, YetiRank / YetiRankPairwise, MAP, MRR, LMS (тест РК проходит в LMS — значит, «Модэл» из лекции 1, вероятно, тоже LMS, а не Moodle), Jupyter, Google Colab. Помимо слайдов к лекции может прилагаться PDF «Доска» — рукописные выкладки без текстового слоя.

**Искажения в готовой расшифровке звонка** (лекция 2; источник — не SpeechKit, а автоматическая расшифровка видеозвонка с метками говорящих; мусорные метки вида «Я:», «Kp:», «Абц:» внутри реплик): Раге / Прагах / рагом / рак → RAG; ретривел → retrieval; Квл, влм → LLM; крутсорсинг → краудсорсинг; сенсорские / асессорской разведки → асессорские / разметки; Dcg, 10 g → DCG; Ncg / Nsg / Ndc / Ntc / Ntcg / Endc / энсиджи / ни Си джи → NDCG; idcg → IDCG; distribution, comulitive game → discounted cumulative gain; point, vice / payer vice / лист, вайс → pointwise / pairwise / listwise; мсье → MSE; Логлос → LogLoss; хинжи → hinge; пранк → PRank; коралл → CORAL; brandknet / рангнет / Ранг net / Антнет → RankNet; лям дранг / лямбда ранг / лямдеранке / λ ранг → LambdaRank; λ лос → LambdaLoss; ем алгоритм → EM-алгоритм; лемпу анкаре / лимпопонкре → лемма Пуанкаре; плаки Люса / плакета люса / лакета люса → Плакетта–Люса; листнет → ListNet; садист. Ml → ListMLE (по смыслу); сигноиду / симоида → сигмоида; бернульевскими → бернуллиевскими; Сгд → SGD; xg буст → XGBoost; как буст / atboost / в катюстяк → CatBoost; етеранг / yeti rang parvis → YetiRank / YetiRankPairwise; perlage и perliet, payer vice → PairLogit и PairLogitPairwise (по смыслу); japai tear / joe party → Jupyter; google коллаб → Google Colab; Лмс → LMS; Мап, Мррр → MAP, MRR; Майкрософт → Microsoft. Правила — в `lectures/r2/work/fix_terms.py`.

Готовые правила для всех строк таблицы — в `lectures/r1/work/fix_terms.py` (список `FIXES`): копируй его в `W/fix_terms.py` новой лекции как основу и дополняй.
