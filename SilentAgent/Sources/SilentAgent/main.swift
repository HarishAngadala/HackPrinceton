import AppKit
import ApplicationServices
import Foundation

private let heyClickyBundleID = "com.humansongs.clicky"
private let leftControlKey: CGKeyCode = 59
private let aKey: CGKeyCode = 0
private let vKey: CGKeyCode = 9
private let commaKey: CGKeyCode = 43
private let returnKey: CGKeyCode = 36
private let escapeKey: CGKeyCode = 53

private struct Options {
    var submit = true
    var timeout: TimeInterval = 6
    var textParts: [String] = []

    static func parse(_ arguments: [String]) throws -> Options {
        var options = Options()
        var index = 0

        while index < arguments.count {
            switch arguments[index] {
            case "--no-submit":
                options.submit = false
            case "--timeout":
                index += 1
                guard index < arguments.count,
                      let timeout = TimeInterval(arguments[index]),
                      timeout > 0,
                      timeout <= 30 else {
                    throw InputError("--timeout must be a number between 0 and 30 seconds")
                }
                options.timeout = timeout
            case "--help", "-h":
                printUsage()
                exit(EXIT_SUCCESS)
            case "--":
                options.textParts.append(contentsOf: arguments.dropFirst(index + 1))
                return options
            default:
                if arguments[index].hasPrefix("-") {
                    throw InputError("unknown option: \(arguments[index])")
                }
                options.textParts.append(arguments[index])
            }
            index += 1
        }
        return options
    }
}

private struct InputError: LocalizedError {
    let message: String
    init(_ message: String) { self.message = message }
    var errorDescription: String? { message }
}

private func printUsage() {
    print("""
    Usage: silent-agent [--no-submit] [--timeout SECONDS] [TEXT ...]

    Sends text through HeyClicky's existing typed input. If TEXT is omitted,
    the exact transcript is read from standard input.

      --no-submit       Fill HeyClicky's input but do not press Send
      --timeout N       Wait up to N seconds for the input (default: 6)

    Examples:
      silent-agent "Open my Notes app"
      printf '%s' "$FLARE_TRANSCRIPT" | silent-agent
      silent-agent --no-submit "Test without running the command"
    """)
}

private func transcript(from options: Options) throws -> String {
    let raw: String
    if !options.textParts.isEmpty {
        raw = options.textParts.joined(separator: " ")
    } else {
        raw = String(data: FileHandle.standardInput.readDataToEndOfFile(), encoding: .utf8) ?? ""
    }

    let text = raw.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !text.isEmpty else {
        throw InputError("no transcript supplied; pass text as an argument or on standard input")
    }
    return text
}

private func copyAttribute(_ element: AXUIElement, _ name: CFString) -> CFTypeRef? {
    var value: CFTypeRef?
    guard AXUIElementCopyAttributeValue(element, name, &value) == .success else { return nil }
    return value
}

private func stringAttribute(_ element: AXUIElement, _ name: CFString) -> String? {
    copyAttribute(element, name) as? String
}

private func boolAttribute(_ element: AXUIElement, _ name: CFString) -> Bool? {
    copyAttribute(element, name) as? Bool
}

private func children(of element: AXUIElement) -> [AXUIElement] {
    copyAttribute(element, kAXChildrenAttribute as CFString) as? [AXUIElement] ?? []
}

private func descendants(of root: AXUIElement, limit: Int = 2_000) -> [AXUIElement] {
    var result: [AXUIElement] = []
    var queue = children(of: root)
    var index = 0

    while index < queue.count, result.count < limit {
        let element = queue[index]
        index += 1
        result.append(element)
        queue.append(contentsOf: children(of: element))
    }
    return result
}

private func isWritableTextInput(_ element: AXUIElement) -> Bool {
    let role = stringAttribute(element, kAXRoleAttribute as CFString)
    guard role == (kAXTextAreaRole as String) || role == (kAXTextFieldRole as String) else {
        return false
    }

    var settable: DarwinBoolean = false
    return AXUIElementIsAttributeSettable(element, kAXValueAttribute as CFString, &settable) == .success
        && settable.boolValue
}

private func windowArea(for element: AXUIElement) -> CGFloat {
    guard let rawWindow = copyAttribute(element, kAXWindowAttribute as CFString),
          CFGetTypeID(rawWindow) == AXUIElementGetTypeID() else {
        return .greatestFiniteMagnitude
    }
    let window = unsafeBitCast(rawWindow, to: AXUIElement.self)
    guard let rawSizeValue = copyAttribute(window, kAXSizeAttribute as CFString),
          CFGetTypeID(rawSizeValue) == AXValueGetTypeID() else {
        return .greatestFiniteMagnitude
    }
    let rawSize = unsafeBitCast(rawSizeValue, to: AXValue.self)
    var size = CGSize.zero
    guard AXValueGetValue(rawSize, .cgSize, &size) else {
        return .greatestFiniteMagnitude
    }
    return size.width * size.height
}

private func postControlTap() throws {
    try runSystemEventsScript("""
        key down control
        delay 0.08
        key up control
        """, purpose: "open HeyClicky's text input")
}

private func runSystemEventsScript(_ body: String, purpose: String) throws {
    let source = """
        tell application "System Events"
        \(body)
        end tell
        """
    guard let script = NSAppleScript(source: source) else {
        throw InputError("could not prepare the keyboard automation used to \(purpose)")
    }
    var details: NSDictionary?
    script.executeAndReturnError(&details)
    if let details {
        let message = details[NSAppleScript.errorMessage] as? String ?? "unknown System Events error"
        throw InputError("could not \(purpose): \(message)")
    }
}

private func postKey(_ key: CGKeyCode, flags: CGEventFlags = []) throws {
    let modifier = flags.contains(.maskCommand) ? " using command down" : ""
    try runSystemEventsScript(
        "key code \(key)\(modifier)",
        purpose: "send keyboard input to HeyClicky"
    )
    Thread.sleep(forTimeInterval: 0.05)
}

private func postCommandComma() throws {
    try postKey(commaKey, flags: .maskCommand)
}

private typealias PasteboardSnapshot = [[NSPasteboard.PasteboardType: Data]]

private func snapshotPasteboard(_ pasteboard: NSPasteboard) -> PasteboardSnapshot {
    (pasteboard.pasteboardItems ?? []).map { item in
        var values: [NSPasteboard.PasteboardType: Data] = [:]
        for type in item.types {
            if let data = item.data(forType: type) {
                values[type] = data
            }
        }
        return values
    }
}

private func restorePasteboard(_ snapshot: PasteboardSnapshot, to pasteboard: NSPasteboard) {
    pasteboard.clearContents()
    let items = snapshot.map { values in
        let item = NSPasteboardItem()
        for (type, data) in values {
            item.setData(data, forType: type)
        }
        return item
    }
    if !items.isEmpty {
        pasteboard.writeObjects(items)
    }
}

private func pasteText(_ text: String, into input: AXUIElement) throws {
    guard AXUIElementSetAttributeValue(input, kAXFocusedAttribute as CFString, kCFBooleanTrue) == .success else {
        throw InputError("could not focus HeyClicky's typed input")
    }
    Thread.sleep(forTimeInterval: 0.08)
    try postKey(aKey, flags: .maskCommand)

    let pasteboard = NSPasteboard.general
    let savedPasteboard = snapshotPasteboard(pasteboard)
    pasteboard.clearContents()
    guard pasteboard.setString(text, forType: .string) else {
        restorePasteboard(savedPasteboard, to: pasteboard)
        throw InputError("could not prepare the transcript for keyboard input")
    }

    do {
        try postKey(vKey, flags: .maskCommand)
        // Let the target app consume the paste before restoring the user's clipboard.
        Thread.sleep(forTimeInterval: 0.2)
    } catch {
        restorePasteboard(savedPasteboard, to: pasteboard)
        throw error
    }
    restorePasteboard(savedPasteboard, to: pasteboard)

    let deadline = Date().addingTimeInterval(1)
    repeat {
        if stringAttribute(input, kAXValueAttribute as CFString) == text { return }
        RunLoop.current.run(until: Date().addingTimeInterval(0.05))
    } while Date() < deadline
    throw InputError("HeyClicky did not accept the transcript as keyboard input")
}

private func pasteTextIntoFocusedInput(_ text: String) throws {
    // The notch composer is a nonstandard floating window. System Events gives
    // it real keyboard focus, while forcing AX focus can select a hidden Home
    // field instead. Keep the complete interaction on the native keyboard path.
    try postKey(aKey, flags: .maskCommand)

    let pasteboard = NSPasteboard.general
    let savedPasteboard = snapshotPasteboard(pasteboard)
    pasteboard.clearContents()
    guard pasteboard.setString(text, forType: .string) else {
        restorePasteboard(savedPasteboard, to: pasteboard)
        throw InputError("could not prepare the transcript for keyboard input")
    }
    do {
        try postKey(vKey, flags: .maskCommand)
        Thread.sleep(forTimeInterval: 0.25)
    } catch {
        restorePasteboard(savedPasteboard, to: pasteboard)
        throw error
    }
    restorePasteboard(savedPasteboard, to: pasteboard)
}

private func openHeyClickyTextInput() throws {
    try postControlTap()
    Thread.sleep(forTimeInterval: 0.09)
    try postControlTap()
}

private func runningHeyClicky() throws -> NSRunningApplication {
    if let app = NSRunningApplication.runningApplications(withBundleIdentifier: heyClickyBundleID).first {
        return app
    }

    guard let url = NSWorkspace.shared.urlForApplication(withBundleIdentifier: heyClickyBundleID) else {
        throw InputError("HeyClicky is not installed")
    }

    guard NSWorkspace.shared.open(url) else {
        throw InputError("HeyClicky could not be opened")
    }
    let deadline = Date().addingTimeInterval(10)
    repeat {
        if let app = NSRunningApplication.runningApplications(withBundleIdentifier: heyClickyBundleID).first {
            return app
        }
        RunLoop.current.run(until: Date().addingTimeInterval(0.1))
    } while Date() < deadline
    throw InputError("HeyClicky did not launch")
}

private func findInput(in root: AXUIElement) -> AXUIElement? {
    let inputs = descendants(of: root).filter(isWritableTextInput)
    // HeyClicky keeps full-size background surfaces in its accessibility tree.
    // The double-Control composer is the smaller foreground panel, so prefer its
    // input instead of a stale field belonging to a hidden Home window.
    return inputs.sorted { left, right in
        let leftArea = windowArea(for: left)
        let rightArea = windowArea(for: right)
        if leftArea != rightArea { return leftArea < rightArea }
        return boolAttribute(left, kAXFocusedAttribute as CFString) == true
            && boolAttribute(right, kAXFocusedAttribute as CFString) != true
    }.first
}

private func findSendButton(in root: AXUIElement) -> AXUIElement? {
    descendants(of: root).first { element in
        guard stringAttribute(element, kAXRoleAttribute as CFString) == (kAXButtonRole as String),
              boolAttribute(element, kAXEnabledAttribute as CFString) != false else {
            return false
        }
        let help = stringAttribute(element, kAXHelpAttribute as CFString)?.lowercased()
        let description = stringAttribute(element, kAXDescriptionAttribute as CFString)?.lowercased()
        let identifier = stringAttribute(element, kAXIdentifierAttribute as CFString)?.lowercased()
        return help == "send" || description == "send" || identifier == "arrow.up"
    }
}

private func findChatButton(in root: AXUIElement) -> AXUIElement? {
    descendants(of: root).first { element in
        guard stringAttribute(element, kAXRoleAttribute as CFString) == (kAXButtonRole as String) else {
            return false
        }
        let description = stringAttribute(element, kAXDescriptionAttribute as CFString)?.lowercased()
        let identifier = stringAttribute(element, kAXIdentifierAttribute as CFString)?.lowercased()
        return description == "chat" || identifier == "bubble.left.and.bubble.right.fill"
    }
}

private func waitForInput(in root: AXUIElement, timeout: TimeInterval) -> AXUIElement? {
    let deadline = Date().addingTimeInterval(timeout)
    repeat {
        if let input = findInput(in: root) { return input }
        RunLoop.current.run(until: Date().addingTimeInterval(0.08))
    } while Date() < deadline
    return nil
}

private func waitForEnabledSendButton(in root: AXUIElement, timeout: TimeInterval) -> AXUIElement? {
    let deadline = Date().addingTimeInterval(timeout)
    repeat {
        if let button = findSendButton(in: root) { return button }
        RunLoop.current.run(until: Date().addingTimeInterval(0.05))
    } while Date() < deadline
    return nil
}

private func waitForSubmission(of text: String, from input: AXUIElement, timeout: TimeInterval) -> Bool {
    let deadline = Date().addingTimeInterval(timeout)
    repeat {
        if stringAttribute(input, kAXValueAttribute as CFString) != text { return true }
        RunLoop.current.run(until: Date().addingTimeInterval(0.05))
    } while Date() < deadline
    return false
}

private func openFullChat(in root: AXUIElement, timeout: TimeInterval) throws -> AXUIElement? {
    try postCommandComma()
    let deadline = Date().addingTimeInterval(timeout)
    repeat {
        if let input = findInput(in: root) { return input }
        if let chatButton = findChatButton(in: root) {
            guard AXUIElementPerformAction(chatButton, kAXPressAction as CFString) == .success else {
                throw InputError("HeyClicky's Chat button could not be opened")
            }
            return waitForInput(in: root, timeout: max(0.2, deadline.timeIntervalSinceNow))
        }
        RunLoop.current.run(until: Date().addingTimeInterval(0.08))
    } while Date() < deadline
    return nil
}

private func send(_ text: String, options: Options) throws {
    // Using the documented key value avoids importing the mutable SDK global into
    // Swift 6's strict-concurrency checking.
    let trustOptions = ["AXTrustedCheckOptionPrompt": true] as CFDictionary
    guard AXIsProcessTrustedWithOptions(trustOptions) else {
        throw InputError("Accessibility permission is required. Enable silent-agent (or the terminal/app launching it) in System Settings > Privacy & Security > Accessibility, then try again")
    }

    let app = try runningHeyClicky()
    app.activate(options: [.activateAllWindows])

    // HeyClicky's native shortcut for typed input is a double-tap of Control.
    // This avoids changing or imitating its voice-recognition path.
    try postKey(escapeKey)
    Thread.sleep(forTimeInterval: 0.15)
    try openHeyClickyTextInput()
    Thread.sleep(forTimeInterval: 0.45)
    try pasteTextIntoFocusedInput(text)

    if !options.submit {
        print("Transcript placed in HeyClicky; Send was not pressed.")
        return
    }

    // Return is HeyClicky's native keyboard submission path.
    try postKey(returnKey)
    Thread.sleep(forTimeInterval: 0.2)
    print("Transcript submitted to HeyClicky as typed input.")
}

do {
    let options = try Options.parse(Array(CommandLine.arguments.dropFirst()))
    try send(transcript(from: options), options: options)
} catch {
    fputs("silent-agent: \(error.localizedDescription)\n", stderr)
    exit(EXIT_FAILURE)
}
