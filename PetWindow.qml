import QtQuick
import Quickshell
import Quickshell.Wayland
import qs.Commons
import "Motion.js" as Motion

// Omagatchi-style transparent, fixed full-monitor layer surface. Only the
// sprite accepts input; a press temporarily expands the region for reliable
// drag even when a cursor outruns the moving pet on an empty workspace.
PanelWindow {
  id: root
  property var profile: null
  property var activity: ({ category: "idle", phrase: "" })
  signal positionRequested(real x, real y)

  readonly property var selectedScreen: {
    var screens = Quickshell.screens
    if (profile && profile.screen) {
      for (var i = 0; i < screens.length; i++)
        if (screens[i].name === profile.screen) return screens[i]
    }
    var biggest = null
    for (var j = 0; j < screens.length; j++)
      if (!biggest || screens[j].width * screens[j].height > biggest.width * biggest.height)
        biggest = screens[j]
    return biggest
  }
  screen: selectedScreen
  visible: !!(profile && profile.enabled && profile.pet && selectedScreen)
  anchors { left: true; right: true; top: true; bottom: true }
  color: "transparent"
  exclusionMode: ExclusionMode.Ignore
  WlrLayershell.layer: WlrLayer.Top
  WlrLayershell.namespace: "omapets"
  WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
  mask: Region { item: grabArea.pressed ? root.contentItem : sprite }

  readonly property real pixelWidth: profile && profile.pet
    ? Math.max(40, Math.round(profile.pet.frameWidth * profile.scale / 4)) : 48
  readonly property real pixelHeight: profile && profile.pet
    ? Math.max(40, Math.round(profile.pet.frameHeight * profile.scale / 4)) : 52
  readonly property string category: activity && activity.category ? activity.category : "idle"
  readonly property var animation: airborne
    ? Motion.airborneAnimation(profile && profile.pet ? profile.pet.rows : 0)
    : profile && profile.animations && profile.animations[category]
    ? profile.animations[category]
    : (walking && category === "idle"
       ? ({ row: facingLeft ? 2 : 1, frames: 8 }) : ({ row: 0, frames: 6 }))
  property int frame: 0
  onCategoryChanged: { frame = 0; frameTick.restart() }
  onWalkingChanged: frame = 0
  onAirborneChanged: frame = 0

  // The profile's x/y are normalized to its monitor, independent of scale.
  property real dragX: -1
  property real dragY: -1
  readonly property real startX: profile && width > 0
    ? Math.max(0, Math.min(width - pixelWidth, profile.position.x * width)) : 0
  readonly property real startY: profile && height > 0
    ? Math.max(0, Math.min(height - pixelHeight, profile.position.y * height)) : 0
  readonly property real groundY: Math.max(0, height - pixelHeight)
  property real fallY: -1
  property real velocityY: 0
  property real velocityX: 0
  property real tossStartedAtMs: -1
  readonly property bool grounded: fallY >= 0 && fallY >= groundY && velocityY === 0
  readonly property bool airborne: fallY >= 0 && !grounded && !grabArea.pressed
  readonly property real petX: dragX >= 0 ? dragX
    : (roamX >= 0 ? roamX : startX)
  readonly property real petY: dragY >= 0 ? dragY : (fallY >= 0 ? fallY : 0)
  property real roamX: -1
  property string renderedPetKey: ""
  property bool walking: false
  property bool facingLeft: false
  property bool infoVisible: false

  function resetPhysics() {
    tossStartedAtMs = -1
    velocityX = 0
    velocityY = 0
    fallY = profile && profile.pet && height > 0 ? 0 : -1
  }

  // A bound PetSlot may receive its initial profile before onProfileChanged
  // is connected. Initialize again at completion/visibility, not only on
  // subsequent profile changes, or the gravity timer stays dormant at -1.
  Component.onCompleted: root.resetPhysics()
  onVisibleChanged: if (visible && fallY < 0) root.resetPhysics()

  onProfileChanged: {
    var nextKey = Motion.petIdentity(profile)
    if (nextKey !== renderedPetKey) {
      renderedPetKey = nextKey
      dragX = -1
      dragY = -1
      roamX = -1
      velocityX = 0
      walking = false
      walkDuration.stop()
      Qt.callLater(root.resetPhysics)
    }
  }
  onHeightChanged: if (profile && profile.pet && fallY < 0) root.resetPhysics()
  onGroundYChanged: if (fallY > groundY) { fallY = groundY; velocityY = 0 }

  // Normal gravity gains 1.1px per 16ms and caps at 24px. After a toss, pull
  // starts at half and recovers over five seconds; the speed cap stays fixed.
  // Bounce is damped, and settled pets need no physics ticks.
  Timer {
    interval: 16
    repeat: true
    running: root.visible && root.fallY >= 0 && !root.grounded && !grabArea.pressed
    onTriggered: {
      if (root.velocityX !== 0) {
        var lateral = Motion.horizontalStep(root.roamX >= 0 ? root.roamX : root.petX, root.velocityX, root.width, root.pixelWidth)
        root.roamX = lateral.x
        root.velocityX = lateral.vx
      }
      var gravityScale = root.tossStartedAtMs < 0 ? 1 : Motion.tossGravityScale(Date.now() - root.tossStartedAtMs)
      var next = Motion.gravityStep(root.fallY, root.velocityY, root.groundY, 0.4, gravityScale)
      root.velocityY = next.vy
      root.fallY = next.y
      if (root.grounded) root.velocityX = 0
    }
  }

  function startRoam() {
    var current = root.roamX >= 0 ? root.roamX : sprite.x
    var direction = Math.random() < 0.5 ? -1 : 1
    var next = Motion.wanderTarget(current, root.width, root.pixelWidth, direction)
    if (next === current) return
    root.facingLeft = next < current
    root.roamX = next
    root.walking = true
    walkDuration.restart()
  }
  Timer {
    interval: 400
    running: root.visible && root.grounded && root.profile
      && root.profile.mode === "wander" && !grabArea.pressed
    onTriggered: root.startRoam()
  }
  Timer {
    interval: 10000
    repeat: true
    running: root.visible && root.grounded && root.profile
      && root.profile.mode === "wander" && !grabArea.pressed
    onTriggered: root.startRoam()
  }
  Timer {
    id: walkDuration
    interval: Motion.speedDuration(root.profile ? root.profile.speed : "slow")
    onTriggered: root.walking = false
  }

  Timer {
    id: frameTick
    interval: Motion.frameInterval(root.airborne, root.walking, root.category)
    repeat: true
    running: root.visible
    onTriggered: root.frame = (root.frame + 1) % Math.max(1, root.animation.frames)
  }
  Timer {
    id: infoTimeout
    interval: 2500
    onTriggered: root.infoVisible = false
  }

  Item {
    id: sprite
    width: root.pixelWidth
    height: root.pixelHeight
    x: root.petX
    y: root.petY
    clip: true
    Behavior on x {
      enabled: root.grounded && root.profile && root.profile.mode === "wander" && !grabArea.pressed
      NumberAnimation {
        duration: Motion.speedDuration(root.profile ? root.profile.speed : "slow")
        easing.type: Easing.InOutQuad
      }
    }

    Image {
      // Moving a single atlas behind a clipped frame is reliable in QtQuick
      // even when a WebP decoder does not honor Image.sourceClipRect.
      width: sprite.width * (root.profile && root.profile.pet ? root.profile.pet.columns : 8)
      height: sprite.height * (root.profile && root.profile.pet ? root.profile.pet.rows : 9)
      x: -root.frame * sprite.width
      y: -root.animation.row * sprite.height
      source: root.profile && root.profile.pet ? root.profile.pet.source : ""
      fillMode: Image.Stretch
      smooth: false
      asynchronous: true
      cache: true
    }

    MouseArea {
      id: grabArea
      anchors.fill: parent
      cursorShape: Qt.PointingHandCursor
      property real pressX: 0
      property real pressY: 0
      property real offsetX: 0
      property real offsetY: 0
      property bool dragged: false
      property var pointerSamples: []

      onPressed: function(mouse) {
        walkDuration.stop()
        root.walking = false
        var point = mapToItem(root.contentItem, mouse.x, mouse.y)
        pressX = point.x
        pressY = point.y
        offsetX = point.x - sprite.x
        offsetY = point.y - sprite.y
        dragged = false
        pointerSamples = [{ x: point.x, y: point.y, t: Date.now() }]
      }
      onPositionChanged: function(mouse) {
        if (!pressed) return
        var point = mapToItem(root.contentItem, mouse.x, mouse.y)
        if (!dragged && Math.abs(point.x - pressX) + Math.abs(point.y - pressY) < 8) return
        dragged = true
        root.dragX = Math.max(0, Math.min(root.width - sprite.width, point.x - offsetX))
        root.dragY = Math.max(0, Math.min(root.height - sprite.height, point.y - offsetY))
        pointerSamples = pointerSamples.slice(-7).concat([{ x: point.x, y: point.y, t: Date.now() }])
      }
      onReleased: function(mouse) {
        if (dragged && root.width > 0 && root.height > 0) {
          var point = mapToItem(root.contentItem, mouse.x, mouse.y)
          root.dragX = Math.max(0, Math.min(root.width - sprite.width, point.x - offsetX))
          root.dragY = Math.max(0, Math.min(root.height - sprite.height, point.y - offsetY))
          var now = Date.now()
          var velocity = Motion.releaseVelocity(pointerSamples, point.x, point.y, now)
          root.tossStartedAtMs = now
          root.roamX = root.dragX
          root.fallY = root.dragY
          root.velocityX = velocity.vx
          root.velocityY = velocity.vy
          root.dragX = -1
          root.dragY = -1
          root.positionRequested(root.roamX / root.width, root.fallY / root.height)
        } else {
          root.infoVisible = true
          infoTimeout.restart()
        }
        dragged = false
        pointerSamples = []
      }
      onCanceled: {
        dragged = false
        pointerSamples = []
        root.dragX = -1
        root.dragY = -1
      }
    }
  }

  Rectangle {
    id: bubble
    readonly property string phrase: root.activity && root.activity.phrase ? root.activity.phrase : ""
    readonly property string message: phrase || (root.infoVisible && root.profile ? root.profile.id : "")
    visible: message !== ""
    x: Math.max(0, Math.min(root.width - width, sprite.x + sprite.width / 2 - width / 2))
    y: sprite.y > height + 8 ? sprite.y - height - 8 : sprite.y + sprite.height + 8
    width: Math.min(280, label.implicitWidth + 20)
    height: label.implicitHeight + 14
    radius: 8
    color: Color.background
    opacity: 0.94
    border.color: Color.foreground
    border.width: 1

    Text {
      id: label
      anchors.centerIn: parent
      text: bubble.message
      textFormat: Text.PlainText
      color: Color.foreground
      font.pixelSize: 12
      width: Math.min(260, implicitWidth)
      wrapMode: Text.Wrap
      horizontalAlignment: Text.AlignHCenter
    }
  }
}
