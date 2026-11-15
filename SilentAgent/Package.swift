// swift-tools-version: 6.2
import PackageDescription

let package = Package(
    name: "SilentAgent",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "silent-agent", targets: ["SilentAgent"]),
    ],
    targets: [
        .executableTarget(name: "SilentAgent"),
    ]
)
