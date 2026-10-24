$docxPath = "C:\Users\ANJALI\.gemini\antigravity\scratch\quickblood\QUICKBLOOD_Project_Document.docx"
$pdfPath = "C:\Users\ANJALI\.gemini\antigravity\scratch\quickblood\QUICKBLOOD_Project_Document.pdf"
$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    $doc = $word.Documents.Open($docxPath)
    $doc.ExportAsFixedFormat($pdfPath, 17) # 17 = wdExportFormatPDF
    Write-Output "PDF Exported successfully: $pdfPath"
    $pages = $doc.ComputeStatistics(2)
    Write-Output "Final Verified Page Count: $pages"
    $doc.Close([ref]$false)
} finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
}
