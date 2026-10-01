import QtQuick
import Quickshell
import Quickshell.Wayland
import qs.Commons
import "Motion.js" as Motion
import "Model.js" as Model

// Omagatchi-style transparent, fixed full-monitor layer surface. Only the
// sprite accepts input; a press temporarily expands the region for reliable
// drag even when a cursor outruns the moving pet on an empty workspace.
PanelWindow {
  id: root
  property var profile: null
  property var activity: ({ category: "idle", phrase: "" })
  property var surfaces: []
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
  readonly property var animation: grabArea.pressed
    ? Motion.heldAnimation(profile && profile.pet ? profile.pet.rows : 0,
                           profile && profile.pet ? profile.pet.columns : 0)
    : airborne ? Motion.airborneAnimation(profile && profile.pet ? profile.pet.rows : 0)
    : profile && profile.animations && profile.animations[category]
    ? profile.animations[category]
    : (walking && category === "idle"
       ? ({ row: facingLeft ? 2 : 1, frames: 8 }) : ({ row: 0, frames: 6 }))
  property int frame: 0
  property int heldPhase: 0
  property real lastPointerMotionMs: -1
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
  property real supportY: -1
  readonly property bool grounded: fallY >= 0 && velocityY === 0
    && (fallY >= groundY || (supportY >= 0 && Math.abs(fallY - supportY) < 1))
  readonly property bool airborne: fallY >= 0 && !grounded && !grabArea.pressed
  readonly property real petX: dragX >= 0 ? dragX
    : (roamX >= 0 ? roamX : startX)
  readonly property real petY: dragY >= 0 ? dragY : (fallY >= 0 ? fallY : 0)
  property real roamX: -1
  property string renderedPetKey: ""
  property bool walking: false
  property bool facingLeft: false
  property bool heldFacingLeft: false
  property real heldSwayAngle: 0
  property bool infoVisible: false

  function resetPhysics() {
    tossStartedAtMs = -1
    supportY = -1
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
      heldSwayAngle = 0
      walking = false
      walkDuration.stop()
      Qt.callLater(root.resetPhysics)
    }
  }
  onHeightChanged: if (profile && profile.pet && fallY < 0) root.resetPhysics()
  onGroundYChanged: if (fallY > groundY) { fallY = groundY; velocityY = 0; supportY = -1 }
  function validateSupport() {
    if (supportY >= 0 && !Motion.supportAt(root.supportY, root.petX,
                                             root.pixelWidth, root.pixelHeight, root.surfaces)) {
      supportY = -1
      velocityY = 0
      walking = false
      walkDuration.stop()
    }
  }
  onSurfacesChanged: root.validateSupport()

  // Normal gravity gains 1.1px per 16ms and caps at 24px. After a toss, pull
  // starts at half and recovers over three seconds; the speed cap stays fixed.
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
      var landing = root.velocityY >= 0
        ? Motion.landingSurface(root.fallY, next.y, root.petX, root.pixelWidth, root.pixelHeight, root.surfaces)
        : null
      if (landing && landing.y >= root.pixelHeight)
        next = Motion.gravityStep(root.fallY, root.velocityY, landing.y - root.pixelHeight, 0.4, gravityScale)
      root.velocityY = next.vy
      root.fallY = next.y
      root.supportY = landing && next.vy === 0 ? next.y : -1
      if (root.grounded) root.velocityX = 0
    }
  }

  function startRoam() {
    var current = root.roamX >= 0 ? root.roamX : sprite.x
    var direction = Math.random() < 0.5 ? -1 : 1
    var next = Motion.wanderTarget(current, root.width, root.pixelWidth, direction)
    if (root.supportY >= 0) {
      var surface = Motion.supportAt(root.supportY, current, root.pixelWidth,
                                     root.pixelHeight, root.surfaces)
      if (surface) next = Motion.wanderOnSurface(current, next, surface, root.pixelWidth)
    }
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
    interval: grabArea.pressed ? 140 : Motion.frameInterval(root.airborne, root.walking, root.category)
    repeat: true
    running: root.visible
    onTriggered: {
      if (grabArea.pressed && root.animation.row === 4) {
        root.heldPhase += 1
        root.frame = Motion.heldFrame(root.heldPhase, Date.now() - root.lastPointerMotionMs < 180)
      } else root.frame = (root.frame + 1) % Math.max(1, root.animation.frames)
    }
  }
  Timer {
    interval: 80
    repeat: true
    running: root.visible && grabArea.pressed
    onTriggered: root.heldSwayAngle = Motion.settleSway(root.heldSwayAngle)
  }
  Timer {
    id: infoTimeout
    interval: 6000
    onTriggered: root.infoVisible = false
  }

  Item {
    id: sprite
    width: root.pixelWidth
    height: root.pixelHeight
    x: root.petX
    y: root.petY
    clip: true
    transformOrigin: Item.Top
    rotation: grabArea.pressed ? root.heldSwayAngle : 0
    transform: Scale {
      origin.x: sprite.width / 2
      origin.y: 0
      xScale: grabArea.pressed && root.heldFacingLeft ? -1 : 1
    }
    Behavior on rotation {
      NumberAnimation { duration: 110; easing.type: Easing.OutQuad }
    }
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
      property real lastPointerX: 0
      property real lastPointerY: 0
      property bool dragged: false
      property var pointerSamples: []

      onPressed: function(mouse) {
        walkDuration.stop()
        root.walking = false
        root.heldPhase = 0
        root.lastPointerMotionMs = Date.now()
        root.frame = Motion.heldAnimation(root.profile.pet.rows, root.profile.pet.columns).row === 4 ? 2 : 0
        frameTick.restart()
        var point = mapToItem(root.contentItem, mouse.x, mouse.y)
        pressX = point.x
        pressY = point.y
        lastPointerX = point.x
        lastPointerY = point.y
        root.heldFacingLeft = root.facingLeft
        root.heldSwayAngle = 0
        var held = Motion.gripPosition(point.x, point.y, root.width, root.height, sprite.width, sprite.height)
        root.dragX = held.x
        root.dragY = held.y
        dragged = false
        pointerSamples = [{ x: point.x, y: point.y, t: Date.now() }]
      }
      onPositionChanged: function(mouse) {
        if (!pressed) return
        var point = mapToItem(root.contentItem, mouse.x, mouse.y)
        root.heldFacingLeft = Motion.heldFacing(lastPointerX, point.x, root.heldFacingLeft)
        root.heldSwayAngle = Motion.heldSway(point.x - lastPointerX)
        if (Math.abs(point.x - lastPointerX) + Math.abs(point.y - lastPointerY) > 1)
          root.lastPointerMotionMs = Date.now()
        lastPointerX = point.x
        lastPointerY = point.y
        if (!dragged && Math.abs(point.x - pressX) + Math.abs(point.y - pressY) < 8) return
        dragged = true
        var held = Motion.gripPosition(point.x, point.y, root.width, root.height, sprite.width, sprite.height)
        root.dragX = held.x
        root.dragY = held.y
        pointerSamples = pointerSamples.slice(-7).concat([{ x: point.x, y: point.y, t: Date.now() }])
      }
      onReleased: function(mouse) {
        if (dragged && root.width > 0 && root.height > 0) {
          root.infoVisible = false
          infoTimeout.stop()
          var point = mapToItem(root.contentItem, mouse.x, mouse.y)
          var held = Motion.gripPosition(point.x, point.y, root.width, root.height, sprite.width, sprite.height)
          root.dragX = held.x
          root.dragY = held.y
          var now = Date.now()
          var velocity = Motion.releaseVelocity(pointerSamples, point.x, point.y, now)
          root.tossStartedAtMs = now
          root.supportY = -1
          root.roamX = root.dragX
          root.fallY = root.dragY
          root.velocityX = velocity.vx
          root.velocityY = velocity.vy
          root.dragX = -1
          root.dragY = -1
          root.positionRequested(root.roamX / root.width, root.fallY / root.height)
        } else {
          root.dragX = -1
          root.dragY = -1
          root.infoVisible = !root.infoVisible
          if (root.infoVisible) infoTimeout.restart()
          else infoTimeout.stop()
        }
        root.heldSwayAngle = 0
        root.frame = 0
        dragged = false
        pointerSamples = []
      }
      onCanceled: {
        dragged = false
        pointerSamples = []
        root.dragX = -1
        root.dragY = -1
        root.heldSwayAngle = 0
        root.frame = 0
      }
    }
  }

  Rectangle {
    id: bubble
    readonly property string message: root.activity && root.activity.phrase ? root.activity.phrase : ""
    visible: message !== "" && !root.infoVisible
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

  // Left click is informational only. The lifecycle event chooses the phrase;
  // showing this card never changes state or samples a fresh response.
  Rectangle {
    id: card
    visible: root.infoVisible && !grabArea.pressed
    width: Math.min(260, Math.max(160, root.width - 16))
    height: cardHeader.implicitHeight + (cardBody.visible ? cardBody.implicitHeight + 8 : 0) + 24
    x: Math.max(0, Math.min(root.width - width, sprite.x + sprite.width / 2 - width / 2))
    y: Math.max(0, sprite.y - height - 8)
    radius: 9
    color: Color.background
    opacity: 0.96
    border.color: Color.foreground
    border.width: 1

    Text {
      id: cardHeader
      x: 12
      y: 10
      width: card.width - 24
      text: (root.profile ? root.profile.id : "Agent") + " · " + Model.statusLabel(root.category)
      textFormat: Text.PlainText
      color: Color.foreground
      font.bold: true
      font.pixelSize: 12
      elide: Text.ElideRight
    }
    Text {
      id: cardBody
      x: 12
      y: cardHeader.y + cardHeader.implicitHeight + 8
      width: card.width - 24
      text: root.activity && root.activity.phrase ? root.activity.phrase : ""
      visible: text !== ""
      textFormat: Text.PlainText
      color: Color.foreground
      font.pixelSize: 12
      wrapMode: Text.Wrap
    }
  }
}
