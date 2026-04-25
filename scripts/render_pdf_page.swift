import Foundation
import PDFKit
import AppKit

if CommandLine.arguments.count < 4 {
    fputs("Usage: render_pdf_page.swift <pdf_path> <page_number> <output_path> [scale]\n", stderr)
    exit(1)
}

let pdfPath = CommandLine.arguments[1]
let pageNumber = Int(CommandLine.arguments[2]) ?? 1
let outputPath = CommandLine.arguments[3]
let scale = CGFloat(Double(CommandLine.arguments.dropFirst(4).first ?? "1.8") ?? 1.8)

let pdfURL = URL(fileURLWithPath: pdfPath)
let outputURL = URL(fileURLWithPath: outputPath)

guard let document = PDFDocument(url: pdfURL),
      let page = document.page(at: pageNumber - 1) else {
    fputs("Failed to load PDF page.\n", stderr)
    exit(1)
}

let bounds = page.bounds(for: .mediaBox)
let renderedSize = NSSize(width: bounds.width * scale, height: bounds.height * scale)
let image = NSImage(size: renderedSize)

image.lockFocus()
guard let context = NSGraphicsContext.current?.cgContext else {
    fputs("Failed to create graphics context.\n", stderr)
    exit(1)
}

context.setFillColor(NSColor.white.cgColor)
context.fill(CGRect(origin: .zero, size: renderedSize))
context.saveGState()
context.translateBy(x: 0, y: renderedSize.height)
context.scaleBy(x: scale, y: -scale)
page.draw(with: .mediaBox, to: context)
context.restoreGState()
image.unlockFocus()

guard let tiffData = image.tiffRepresentation,
      let bitmap = NSBitmapImageRep(data: tiffData),
      let pngData = bitmap.representation(using: .png, properties: [:]) else {
    fputs("Failed to encode PNG.\n", stderr)
    exit(1)
}

try FileManager.default.createDirectory(
    at: outputURL.deletingLastPathComponent(),
    withIntermediateDirectories: true,
)
try pngData.write(to: outputURL)
print(outputPath)
