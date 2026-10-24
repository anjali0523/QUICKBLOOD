$filePath = "C:\Users\ANJALI\.gemini\antigravity\scratch\quickblood\QUICKBLOOD_Project_Document.docx"
$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    $doc = $word.Documents.Open($filePath)
    $pages = $doc.ComputeStatistics(2) # 2 = wdStatisticPages
    Write-Output "PAGE_COUNT: $pages"
    $doc.Close([ref]$false)
} finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
}
