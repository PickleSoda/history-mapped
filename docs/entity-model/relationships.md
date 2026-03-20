# Relationship Types — Complete Reference

A **relationship** connects two entities — a *source* and a *target* — with a named type, an optional time window, and an optional confidence level.

Relationships are **directed**: the arrow goes from source to target. The direction is part of the meaning.

> *Julius Caesar* **[rules]** *Roman Republic* means Caesar is the ruler; the Republic is the governed entity.

Many relationship types have a natural inverse. Where useful, both directions can be stored as separate records.

---

## How to Read the Tables

| Column | Meaning |
|---|---|
| Type value | The internal identifier used in the system |
| Description | What the relationship asserts |
| Typical source | What kind of entity usually appears as the source |
| Typical target | What kind of entity usually appears as the target |
| Example | A concrete historical instance |

---

## Political Relationships

These describe the exercise of power, territorial organisation, and the life cycle of states.

| Type | Description | Typical source | Typical target | Example |
|---|---|---|---|---|
| `rules` | The source entity governs or exercises sovereign authority over the target | Person, dynasty | Political entity, city | *Augustus* **[rules]** *Roman Empire* |
| `governed_by` | The target is the ruler of the source (inverse of `rules`) | Political entity | Person, dynasty | *Roman Empire* **[governed_by]** *Augustus* |
| `vassal_of` | The source owes fealty or tribute to the target | Political entity | Political entity | *Duchy of Saxony* **[vassal_of]** *Holy Roman Empire* |
| `suzerain_of` | The source exercises overlordship over the target (inverse of `vassal_of`) | Political entity | Political entity | *Holy Roman Empire* **[suzerain_of]** *Duchy of Saxony* |
| `allied_with` | The source and target are formally allied | Political entity | Political entity | *Athens* **[allied_with]** *Sparta* (against Persia, 480 BCE) |
| `at_war_with` | The source and target are in a state of war | Political entity | Political entity | *Rome* **[at_war_with]** *Carthage* (264–241 BCE) |
| `succeeded_by` | The target entity directly replaced the source | Political entity | Political entity | *Roman Republic* **[succeeded_by]** *Roman Principate* |
| `preceded_by` | The target existed before and was replaced by the source (inverse of `succeeded_by`) | Political entity | Political entity | *Roman Principate* **[preceded_by]** *Roman Republic* |
| `part_of` | The source is a constituent part of the target | Political entity, place | Political entity | *Kingdom of Naples* **[part_of]** *Kingdom of the Two Sicilies* |
| `contains` | The source contains the target as a constituent part (inverse of `part_of`) | Political entity | Political entity, place | *Mongol Empire* **[contains]** *Il-Khanate* |
| `capital_of` | The source city is the capital of the target state | City | Political entity | *Constantinople* **[capital_of]** *Byzantine Empire* |
| `split_from` | The source entity broke away from the target | Political entity | Political entity | *Eastern Roman Empire* **[split_from]** *Roman Empire* |
| `merged_into` | The source entity was absorbed into or unified with the target | Political entity | Political entity | *Crown of Castile* **[merged_into]** *Kingdom of Spain* |

---

## Person Relationships

These describe what individuals did and how they related to states, places, events, and each other.

| Type | Description | Typical source | Typical target | Example |
|---|---|---|---|---|
| `born_in` | The source person was born in the target place | Person | City, political entity | *Confucius* **[born_in]** *Qufu* |
| `died_in` | The source person died in the target place | Person | City, political entity | *Alexander the Great* **[died_in]** *Babylon* |
| `resided_in` | The source person lived in the target place (use temporal window) | Person | City, political entity | *Ibn Battuta* **[resided_in]** *Mali Empire* (1352–1353) |
| `commanded` | The source person commanded the target military unit or army | Person | Military unit | *Khalid ibn al-Walid* **[commanded]** *Rashidun Army* |
| `founded` | The source person or entity established the target | Person, political entity | Political entity, city, institution | *Alexander the Great* **[founded]** *Alexandria* |
| `authored` | The source person created the target cultural work | Person | Cultural work, religious text, legal code | *Dante Alighieri* **[authored]** *Divine Comedy* |
| `commissioned` | The source ordered or financed the creation of the target | Person, political entity | Cultural work, infrastructure | *Qin Shi Huang* **[commissioned]** *Great Wall of China* |
| `married_to` | The source and target are spouses (use temporal window) | Person | Person | *Henry VIII* **[married_to]** *Anne Boleyn* (1533–1536) |
| `parent_of` | The source is the biological or adoptive parent of the target | Person | Person | *Cleopatra VII* **[parent_of]** *Caesarion* |
| `child_of` | The source is the biological or adoptive child of the target (inverse) | Person | Person | *Caesarion* **[child_of]** *Julius Caesar* |
| `sibling_of` | The source and target share a parent | Person | Person | *Aurangzeb* **[sibling_of]** *Dara Shikoh* |
| `mentor_of` | The source taught or mentored the target | Person | Person | *Aristotle* **[mentor_of]** *Alexander the Great* |
| `student_of` | The source was taught by the target (inverse) | Person | Person | *Alexander the Great* **[student_of]** *Aristotle* |
| `assassinated_by` | The source was killed by the target | Person | Person, military unit | *Julius Caesar* **[assassinated_by]** *Senate conspirators* |
| `member_of_dynasty` | The source person belongs to the target dynasty or lineage | Person | Dynasty | *Nero* **[member_of_dynasty]** *Julio-Claudian dynasty* |
| `patron_of` | The source provided financial or political support for the target's work | Person, political entity | Person, cultural work | *Lorenzo de' Medici* **[patron_of]** *Sandro Botticelli* |

---

## Military Relationships

These describe the participation of forces, states, and persons in armed conflict.

| Type | Description | Typical source | Typical target | Example |
|---|---|---|---|---|
| `participated_in` | The source took part in the target conflict or battle | Political entity, military unit | Event (war, battle) | *Sparta* **[participated_in]** *Persian Wars* |
| `fought_at` | The source engaged in combat at the target location or battle | Military unit, political entity | Event (battle), city | *Roman Legions* **[fought_at]** *Battle of Cannae* |
| `defeated_at` | The source was the losing side at the target battle | Political entity, military unit | Event (battle) | *Darius III* **[defeated_at]** *Battle of Gaugamela* |
| `victorious_at` | The source was the winning side at the target battle | Political entity, military unit | Event (battle) | *Alexander the Great* **[victorious_at]** *Battle of Gaugamela* |
| `stationed_at` | The source force was garrisoned at the target location | Military unit | City, place | *Roman Legions* **[stationed_at]** *Hadrian's Wall* |
| `recruited_from` | The source force drew its soldiers from the target region or group | Military unit | Political entity, social class | *Janissaries* **[recruited_from]** *devshirme system* |
| `commanded_by` | The source force was under the command of the target person | Military unit | Person | *Mongol army* **[commanded_by]** *Subutai* |

---

## Economic Relationships

These describe trade, production, resource extraction, and monetary systems.

| Type | Description | Typical source | Typical target | Example |
|---|---|---|---|---|
| `trades_with` | The source entity engaged in trade with the target | Political entity | Political entity | *Venice* **[trades_with]** *Byzantine Empire* |
| `connects` | The source route links the target places (use multiple instances) | Trade route | City, political entity | *Silk Road* **[connects]** *Chang'an* |
| `produces` | The source entity produces or exports the target commodity | Political entity, place | Natural resource | *Egypt* **[produces]** *papyrus* |
| `extracts` | The source extracts the target resource from its location | Political entity, extraction infra | Natural resource | *Potosí mines* **[extracts]** *silver* |
| `supplies` | The source entity provides the target commodity or resource to another entity | Political entity, trade route | Natural resource | *Silk Road* **[supplies]** *silk to Rome* |
| `controlled_by` | The source resource or route is under the authority of the target | Trade route, natural resource | Political entity | *Mediterranean trade routes* **[controlled_by]** *Rome* |
| `passes_through` | The source route traverses the territory of the target | Trade route | Political entity, place | *Silk Road* **[passes_through]** *Parthian Empire* |
| `minted_by` | The source currency was issued by the target authority | Currency | Political entity | *Roman denarius* **[minted_by]** *Roman Republic* |
| `used_currency` | The source entity's economy used the target currency | Political entity | Currency | *Byzantine Empire* **[used_currency]** *solidus* |

---

## Religious and Cultural Relationships

These describe the spread of beliefs, the creation and influence of works, the construction and destruction of places, and cultural borrowing.

| Type | Description | Typical source | Typical target | Example |
|---|---|---|---|---|
| `adheres_to` | The source entity professes or is associated with the target religion or movement | Political entity, person | Religious movement | *Akbar* **[adheres_to]** *Din-i-Ilahi* |
| `official_religion_of` | The target state has adopted the source religion as its official faith | Religious movement | Political entity | *Christianity* **[official_religion_of]** *Roman Empire* (after 380 CE) |
| `persecuted_by` | The source group or movement was violently suppressed by the target | Religious movement, social class | Political entity | *Early Christians* **[persecuted_by]** *Roman Empire* |
| `influenced_by` | The source was shaped by ideas, practices, or styles from the target | Cultural work, intellectual movement, person | Cultural work, intellectual movement | *Scholasticism* **[influenced_by]** *Aristotelian philosophy* |
| `inspired` | The source gave rise to or stimulated the target (inverse of `influenced_by`) | Cultural work, intellectual movement | Cultural work, person | *Plato's Academy* **[inspired]** *Neoplatonism* |
| `schism_from` | The source broke away from the target religious body | Religious movement | Religious movement | *Protestantism* **[schism_from]** *Catholic Church* |
| `translated_into` | The source text was rendered into the target language (or the target is a translated version) | Cultural work, religious text | Language, cultural work | *Aristotle's works* **[translated_into]** *Arabic* (Abbasid Translation Movement) |
| `located_at` | The source cultural or religious entity is physically situated at the target place | Educational institution, infrastructure monument | City, place | *Library of Alexandria* **[located_at]** *Alexandria* |
| `built_by` | The source structure or monument was constructed by the target entity | Infrastructure monument | Political entity, person | *Hagia Sophia* **[built_by]** *Justinian I* |
| `destroyed_by` | The source place or work was destroyed by the target | City, infrastructure monument, cultural work | Political entity, event | *Library of Alexandria* **[destroyed_by]** *Caesar's fire (48 BCE)* |
| `restored_by` | The source was rebuilt or restored by the target after damage or destruction | Infrastructure monument, city | Political entity, person | *Temple of Jerusalem* **[restored_by]** *Herod the Great* |

---

## Causal Relationships

These describe why things happened — causes, consequences, and enabling or inhibiting factors.

| Type | Description | Example |
|---|---|---|
| `caused` | The source directly brought about the target event or outcome | *Assassination of Franz Ferdinand* **[caused]** *World War I* |
| `resulted_from` | The source is a consequence of the target (inverse of `caused`) | *World War I* **[resulted_from]** *Assassination of Franz Ferdinand* |
| `contributed_to` | The source was one among several factors that brought about the target | *Black Death* **[contributed_to]** *Decline of feudalism* |
| `enabled` | The source made the target possible without directly causing it | *Printing press* **[enabled]** *Protestant Reformation* |
| `prevented` | The source stopped or forestalled the target from occurring | *Battle of Tours (732)* **[prevented]** *Frankish conquest by Umayyads* |
| `weakened` | The source reduced the power, resources, or stability of the target | *Plague of Justinian* **[weakened]** *Byzantine Empire* |
| `strengthened` | The source increased the power, resources, or stability of the target | *Silk Road revenues* **[strengthened]** *Tang Dynasty* |

---

## Knowledge and Technology Relationships

These describe how knowledge, techniques, and innovations spread and transformed across societies.

| Type | Description | Example |
|---|---|---|
| `invented` | The source person or society created the target technology or technique | *China* **[invented]** *paper* |
| `adopted` | The source entity took up and put into use the target technology or practice | *Islamic world* **[adopted]** *paper* (from China, 8th century) |
| `taught_at` | The source body of knowledge was studied or transmitted at the target institution | *Greek philosophy* **[taught_at]** *Plato's Academy* |
| `spread_to` | The source knowledge, religion, or practice diffused to the target region or society | *Buddhism* **[spread_to]** *China* (via Silk Road) |
| `required_by` | The target technology or institution depended on the source as a prerequisite | *Writing* **[required_by]** *bureaucratic state* |
| `replaced_by` | The source was superseded by the target innovation or practice | *bronze tools* **[replaced_by]** *iron tools* |

---

## Diplomatic Relationships

These describe formal treaties and diplomatic instruments as active entities that affect the states party to them.

| Type | Description | Typical source | Typical target | Example |
|---|---|---|---|---|
| `signed_by` | The source treaty was agreed to by the target entity | Event (treaty) | Political entity | *Peace of Westphalia* **[signed_by]** *Holy Roman Empire* |
| `violated_by` | The source treaty was broken by the target | Event (treaty) | Political entity | *Non-Aggression Pact (1939)* **[violated_by]** *Nazi Germany* (1941) |
| `guaranteed_by` | The source agreement was guaranteed or underwritten by the target power | Event (treaty) | Political entity | *Treaty of Berlin (1878)* **[guaranteed_by]** *Great Powers* |
| `mediated_by` | The source agreement was brokered by the target | Event (treaty) | Person, political entity | *Peace of Augsburg* **[mediated_by]** *Ferdinand I* |
| `enforced_by` | The source agreement was enforced by the target military or political power | Event (treaty) | Political entity | *Versailles Treaty* **[enforced_by]** *League of Nations* |

---

## Temporal Windows on Relationships

Any relationship can carry a `temporal_start` and `temporal_end` to indicate when the relationship held. This is essential for situations that changed over time:

> *Athens* **[allied_with]** *Sparta* — temporal_start: `−480`, temporal_end: `−479`
> (The alliance lasted only for the Persian Wars; they were enemies before and after.)

> *Silk Road* **[controlled_by]** *Han Dynasty* — temporal_start: `−130`, temporal_end: `220`

When the time window is unknown, leave both fields blank — the relationship is simply asserted as having existed at some point within the entities' lifespans.

---

## Confidence on Relationships

Relationships can carry the same `confidence` levels as entities: `high`, `medium`, `low`, or `unresolved`.

Use `low` or `unresolved` when:
- The relationship is attested in a single, potentially unreliable source
- The source uses ambiguous language ("may have allied with…")
- There is scholarly disagreement about whether the relationship existed

Always add a source citation to support any relationship with confidence below `high`.
