pragma ComponentBehavior: Bound
import QtQuick
import qs.Commons
import qs.Ui

// One widget per configured bar/monitor; all shared state lives in Service.qml.
BarWidget {
  id: root
  moduleName: "io.github.zombie-w33d.omapets"
  readonly property var petService: bar && bar.shell
    ? bar.shell.serviceFor(root.moduleName) : null
  readonly property int activeCount: petService ? petService.renderableProfiles.length : 0
  property bool opened: false

  function open() { opened = true }
  function close() { opened = false }
  function toggle() { opened = !opened }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.vertical ? "🐾" : ("🐾 " + root.activeCount)
    tooltipText: "OmaPets — manage local Hermes companions"
    onPressed: function(mouseButton) {
      if (mouseButton === Qt.LeftButton) root.toggle()
      else if (mouseButton === Qt.MiddleButton && root.petService) root.petService.refresh()
    }
  }

  PopupCard {
    id: popup
    anchorItem: root
    bar: root.bar
    owner: root
    open: root.opened
    contentWidth: popup.fittedContentWidth(Style.space(390))
    contentHeight: popup.fittedContentHeight(contents.implicitHeight)

    Column {
      id: contents
      anchors.fill: parent
      spacing: Style.space(10)

      Text {
        text: "OmaPets · " + root.activeCount + " visible"
        textFormat: Text.PlainText
        font.bold: true
        color: root.bar ? root.bar.foreground : Color.foreground
      }
      Text {
        visible: !root.petService || root.petService.profiles.length === 0
        text: root.petService ? "No local Hermes profiles found" : "OmaPets service unavailable"
        textFormat: Text.PlainText
        color: root.bar ? root.bar.foreground : Color.foreground
      }
      Text {
        visible: root.petService && root.petService.lastError !== ""
        text: root.petService ? root.petService.lastError : ""
        textFormat: Text.PlainText
        width: parent.width
        wrapMode: Text.Wrap
        color: Color.foreground
      }
      Text {
        visible: root.petService && root.petService.petIds.length === 0
        text: "Add a local OpenPets character in ~/.hermes/pets first"
        textFormat: Text.PlainText
        width: parent.width
        wrapMode: Text.Wrap
        color: root.bar ? root.bar.foreground : Color.foreground
      }

      Repeater {
        model: root.petService ? root.petService.profiles : []
        delegate: Column {
          id: profileRow
          required property var modelData
          width: contents.width
          spacing: Style.space(3)

          Text {
            text: profileRow.modelData.id + (profileRow.modelData.petId ? " · " + profileRow.modelData.petId : "")
            textFormat: Text.PlainText
            width: parent.width
            elide: Text.ElideRight
            color: root.bar ? root.bar.foreground : Color.foreground
          }
          Row {
            spacing: Style.space(5)
            Button {
              text: profileRow.modelData.enabled ? "Hide" : "Show"
              foreground: root.bar ? root.bar.foreground : Color.foreground
              enabled: !!root.petService && (profileRow.modelData.enabled || root.petService.petIds.length > 0)
              onClicked: root.petService.configure(profileRow.modelData.id, "enabled", profileRow.modelData.enabled ? "false" : "true")
            }
            Button {
              text: profileRow.modelData.mode === "stay" ? "Stay" : "Wander"
              foreground: root.bar ? root.bar.foreground : Color.foreground
              enabled: !!root.petService
              onClicked: root.petService.configure(profileRow.modelData.id, "mode", profileRow.modelData.mode === "stay" ? "wander" : "stay")
            }
            Button {
              text: "Next character"
              foreground: root.bar ? root.bar.foreground : Color.foreground
              enabled: !!root.petService && root.petService.petIds.length > 1
              onClicked: {
                var pets = root.petService.petIds
                var current = pets.indexOf(profileRow.modelData.petId)
                root.petService.configure(profileRow.modelData.id, "petId", pets[(current + 1) % pets.length])
              }
            }
          }
          Button {
            text: "Wander speed: " + (profileRow.modelData.speed || "slow")
            foreground: root.bar ? root.bar.foreground : Color.foreground
            enabled: !!root.petService && profileRow.modelData.mode === "wander"
            onClicked: {
              var speeds = ["slow", "normal", "brisk"]
              var current = speeds.indexOf(profileRow.modelData.speed)
              root.petService.configure(profileRow.modelData.id, "speed", speeds[(current + 1) % speeds.length])
            }
          }
          Text {
            visible: profileRow.modelData.error !== ""
            text: profileRow.modelData.error
            textFormat: Text.PlainText
            width: parent.width
            wrapMode: Text.Wrap
            color: Color.foreground
          }
        }
      }
      Text {
        text: "Drag a pet and release to let it fall. Settings stay per agent."
        textFormat: Text.PlainText
        width: parent.width
        wrapMode: Text.Wrap
        color: root.bar ? root.bar.foreground : Color.foreground
      }
      Button {
        text: "Refresh profiles"
        foreground: root.bar ? root.bar.foreground : Color.foreground
        enabled: !!root.petService
        onClicked: root.petService.refresh()
      }
    }
  }
}
