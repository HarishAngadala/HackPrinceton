import AppKit
import ApplicationServices
import Foundation

private let heyClickyBundleID = "com.humansongs.clicky"
private let leftControlKey: CGKeyCode = 59
private let commaKey: CGKeyCode = 43

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

private func postControlTap() throws {
    guard let down = CGEvent(keyboardEventSource: nil, virtualKey: leftControlKey, keyDown: true),
          let up = CGEvent(keyboardEventSource: nil, virtualKey: leftControlKey, keyDown: false) else {
        throw InputError("could not create the keyboard event used to open HeyClicky's text input")
    }
    down.flags = .maskControl
    up.flags = []
    down.post(tap: .cghidEventTap)
    up.post(tap: .cghidEventTap)
}

private func postCommandComma() throws {
    guard let down = CGEvent(keyboardEventSource: nil, virtualKey: commaKey, keyDown: true),
          let up = CGEvent(keyboardEventSource: nil, virtualKey: commaKey, keyDown: false) else {
        throw InputError("could not create the keyboard event used to open HeyClicky")
    }
    down.flags = .maskCommand
    up.flags = .maskCommand
    down.post(tap: .cghidEventTap)
    up.post(tap: .cghidEventTap)
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
    return inputs.first(where: { boolAttribute($0, kAXFocusedAttribute as CFString) == true }) ?? inputs.first
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
    let root = AXUIElementCreateApplication(app.processIdentifier)

    // HeyClicky's native shortcut for typed input is a double-tap of Control.
    // This avoids changing or imitating its voice-recognition path.
    try openHeyClickyTextInput()
    let shortcutWait = min(1.5, options.timeout)
    let input: AXUIElement?
    if let shortcutInput = waitForInput(in: root, timeout: shortcutWait) {
        input = shortcutInput
    } else {
        input = try openFullChat(in: root, timeout: options.timeout - shortcutWait)
    }

    guard let input else {
        throw InputError("HeyClicky's typed input did not appear")
    }
    guard AXUIElementSetAttributeValue(input, kAXValueAttribute as CFString, text as CFTypeRef) == .success else {
        throw InputError("could not place the transcript in HeyClicky's typed input")
    }
    _ = AXUIElementSetAttributeValue(input, kAXFocusedAttribute as CFString, kCFBooleanTrue)

    if !options.submit {
        print("Transcript placed in HeyClicky; Send was not pressed.")
        return
    }

    guard let sendButton = waitForEnabledSendButton(in: root, timeout: 1.5) else {
        throw InputError("the transcript was inserted, but HeyClicky's Send button did not become available; the text was left for review")
    }
    guard AXUIElementPerformAction(sendButton, kAXPressAction as CFString) == .success else {
        throw InputError("the transcript was inserted, but HeyClicky's Send button could not be pressed; the text was left for review")
    }
    print("Transcript submitted to HeyClicky as typed input.")
}

do {
    let options = try Options.parse(Array(CommandLine.arguments.dropFirst()))
    try send(transcript(from: options), options: options)
} catch {
    fputs("silent-agent: \(error.localizedDescription)\n", stderr)
    exit(EXIT_FAILURE)
}
