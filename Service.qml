pragma ComponentBehavior: Bound
import QtQuick
import Quickshell.Io
import "Model.js" as Model

// This service is mounted once by Omarchy. No second Quickshell instance,
// network listener, Hermes session probe or global shell configuration change.
Item {
  id: root
  property string omarchyPath: ""
  property var shell: null
  property var manifest: null

  readonly property string pluginId: "io.github.zombie-w33d.omapets"
  readonly property string helperPath: decodeURIComponent(String(Qt.resolvedUrl("scripts/omapets_cli.py")).replace(/^file:\/\//, ""))
  property var profiles: []
  property var petIds: []
  property var activity: ({})
  property string previousSnapshot: ""
  property double nowMs: Date.now()
  property bool refreshing: false
  property string lastError: ""
  readonly property var renderableProfiles: profiles.filter(function(p) {
    return p.enabled === true && p.pet !== null
  })

  function refresh() {
    if (root.refreshing || snapshotProcess.running) return
    root.refreshing = true
    root.lastError = ""
    snapshotProcess.command = ["/usr/bin/python3", "-I", root.helperPath, "snapshot"]
    snapshotProcess.running = true
    snapshotDeadline.restart()
  }

  function updateSnapshot(text) {
    if (text.length > 49152) throw new Error("snapshot exceeded the memory budget")
    if (text === root.previousSnapshot) return
    var parsed = JSON.parse(text)
    if (parsed.schemaVersion !== 1 || !Array.isArray(parsed.profiles)
        || !Array.isArray(parsed.petIds) || parsed.profiles.length > 12
        || parsed.petIds.length > 32) throw new Error("invalid snapshot")
    root.petIds = parsed.petIds
    root.profiles = parsed.profiles
    root.previousSnapshot = text
    var kept = ({})
    for (var i = 0; i < parsed.profiles.length; i++) {
      var entry = parsed.profiles[i]
      if (entry.enabled === true && entry.pet && root.activity[entry.id])
        kept[entry.id] = root.activity[entry.id]
    }
    root.activity = kept
  }

  function profileById(id) {
    for (var i = 0; i < root.profiles.length; i++)
      if (root.profiles[i].id === id) return root.profiles[i]
    return null
  }

  function profileAt(index) {
    return index < root.renderableProfiles.length ? root.renderableProfiles[index] : null
  }

  function activityFor(id) {
    return Model.visibleEvent(root.activity[id], root.nowMs)
  }

  function emitEvent(id, category) {
    var event = Model.applyEvent(root.profiles, root.activity, id, category, Date.now(), Math.random)
    if (!event) return false
    var next = ({})
    for (var existing in root.activity) next[existing] = root.activity[existing]
    next[id] = event
    root.activity = next
    root.nowMs = Date.now()
    return true
  }

  // Only a deliberate local UI action calls this method. IPC cannot mutate
  // config; CLI revalidates both the profile and all requested fields.
  function configure(id, field, value) {
    if (settingsProcess.running || root.refreshing || !root.profileById(id)) return false
    if (["enabled", "mode", "petId", "position", "scale", "screen"].indexOf(field) === -1) return false
    settingsProcess.command = ["/usr/bin/python3", "-I", root.helperPath,
                               "set", id, field, String(value)]
    root.lastError = ""
    settingsProcess.running = true
    settingsDeadline.restart()
    return true
  }

  IpcHandler {
    target: "io.github.zombie-w33d.omapets"
    function refresh(): void { root.refresh() }
    function event(profileId: string, category: string): string {
      return root.emitEvent(profileId, category) ? "ok" : "ignored"
    }
    function status(): string {
      return JSON.stringify({
        profiles: root.profiles.length, visible: root.renderableProfiles.length,
        refreshing: root.refreshing, error: root.lastError.slice(0, 120)
      })
    }
  }

  Process {
    id: snapshotProcess
    stdout: StdioCollector { id: snapshotOutput; waitForEnd: true }
    stderr: StdioCollector { id: snapshotError; waitForEnd: true }
    onExited: function(exitCode) {
      snapshotDeadline.stop()
      root.refreshing = false
      if (exitCode !== 0) {
        root.lastError = "Could not read local pet settings: " + String(snapshotError.text).slice(0, 120)
        return
      }
      try { root.updateSnapshot(snapshotOutput.text) }
      catch (error) { root.lastError = "Could not parse local pet settings" }
    }
  }

  Timer {
    id: snapshotDeadline
    interval: 4000
    onTriggered: {
      snapshotProcess.running = false
      root.refreshing = false
      root.lastError = "Reading local pet settings timed out"
    }
  }

  Process {
    id: settingsProcess
    stdout: StdioCollector { waitForEnd: true }
    stderr: StdioCollector { id: settingsError; waitForEnd: true }
    onExited: function(exitCode) {
      settingsDeadline.stop()
      if (exitCode !== 0)
        root.lastError = "Could not save pet settings: " + String(settingsError.text).slice(0, 120)
      root.refresh()
    }
  }

  Timer {
    id: settingsDeadline
    interval: 4000
    onTriggered: {
      settingsProcess.running = false
      root.lastError = "Saving pet settings timed out"
    }
  }

  Timer {
    interval: 30000
    repeat: true
    running: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }
  Timer {
    interval: 1000
    repeat: true
    running: root.renderableProfiles.length > 0
    onTriggered: root.nowMs = Date.now()
  }

  // Static slots avoid dynamic layer-surface destruction on plugin reload;
  // Omagatchi observed zombie layer surfaces when windows were Loader-created.
  // Each slot is independently masked; disabled slots remain invisible.
  component PetSlot: PetWindow {
    required property int slotIndex
    profile: root.profileAt(slotIndex)
    activity: root.activityFor(profile ? profile.id : "")
    onPositionRequested: function(x, y) {
      if (profile) root.configure(profile.id, "position", x.toFixed(4) + "," + y.toFixed(4))
    }
  }
  PetSlot { slotIndex: 0 }
  PetSlot { slotIndex: 1 }
  PetSlot { slotIndex: 2 }
  PetSlot { slotIndex: 3 }
  PetSlot { slotIndex: 4 }
  PetSlot { slotIndex: 5 }
  PetSlot { slotIndex: 6 }
  PetSlot { slotIndex: 7 }
  PetSlot { slotIndex: 8 }
  PetSlot { slotIndex: 9 }
  PetSlot { slotIndex: 10 }
  PetSlot { slotIndex: 11 }
}
