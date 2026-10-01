var CATEGORIES = ["thinking", "waiting_on_you", "waiting_on_task", "yes", "no", "success", "finished", "failed"]

function applyEvent(profiles, active, profileId, category, now, random) {
  if (typeof profileId !== "string" || profileId.length > 64
      || typeof category !== "string" || CATEGORIES.indexOf(category) === -1) return null
  var profile = null
  for (var i = 0; i < profiles.length; i++) {
    if (profiles[i].id === profileId) { profile = profiles[i]; break }
  }
  if (!profile || profile.enabled !== true || !profile.pet) return null
  var phrases = profile.phrases && Array.isArray(profile.phrases[category])
    ? profile.phrases[category] : []
  var previous = active[profileId] ? active[profileId].phrase : ""
  var pool = phrases.length > 1 ? phrases.filter(function(line) { return line !== previous }) : phrases
  if (pool.length === 0) pool = phrases
  var value = pool.length > 0 ? pool[Math.floor(random() * pool.length)] : ""
  return { category: category, phrase: value, time: now }
}

function visibleEvent(event, now) {
  if (!event || typeof event.time !== "number") return { category: "idle", phrase: "" }
  var transient = ["yes", "no", "success", "finished", "failed"].indexOf(event.category) !== -1
  var duration = transient ? 8000 : 120000
  if (now - event.time >= duration || now < event.time) return { category: "idle", phrase: "" }
  return event
}
