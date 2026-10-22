param([Parameter(Mandatory=$true)][string]$InputPath,[Parameter(Mandatory=$true)][string]$PdfPath)
$ErrorActionPreference='Stop'
$resolvedInput=[System.IO.Path]::GetFullPath($InputPath)
if ($resolvedInput -ne 'D:\VTP\Do_an_tot_nghiep_PhuYen_BG_Flood_SAR_chinh_sua_20261005.docx') {throw 'Unexpected input document'}
$taskWord=$null
$taskDocument=$null
$ownsInstance=$false
try {
    $taskWord=New-Object -ComObject Word.Application
    if ($taskWord.Documents.Count -ne 0) {throw 'Word returned an instance with existing documents'}
    $ownsInstance=$true
    $taskWord.Visible=$false
    $taskWord.DisplayAlerts=0
    $taskWord.Options.UpdateLinksAtOpen=$false
    $taskDocument=$taskWord.Documents.Open($resolvedInput,$false,$false,$false)
    foreach ($styleName in @('TOC 1','TOC 2','TOC 3','Table of Figures')) {
        $taskStyle=$taskDocument.Styles.Item($styleName)
        $taskStyle.Font.Name='Times New Roman'
        $taskStyle.Font.Size=11.5
        $taskStyle.Font.Color=0
        $taskStyle.Font.Bold=0
        $taskStyle.ParagraphFormat.FirstLineIndent=0
        $taskStyle.ParagraphFormat.SpaceAfter=3
        $taskStyle.ParagraphFormat.SpaceBefore=0
        $taskStyle.ParagraphFormat.LineSpacingRule=0
    }
    $taskDocument.Styles.Item('TOC 1').ParagraphFormat.LeftIndent=0
    $taskDocument.Styles.Item('TOC 2').ParagraphFormat.LeftIndent=14.17
    $taskDocument.Styles.Item('TOC 3').ParagraphFormat.LeftIndent=28.35
    $taskDocument.Styles.Item('Hyperlink').Font.Color=0
    $taskDocument.Styles.Item('Hyperlink').Font.Underline=0
    # Hyperlinks are created only in the bibliography, never from local run paths.
    foreach ($taskParagraph in $taskDocument.Paragraphs) {
        $taskText=$taskParagraph.Range.Text
        if ($taskText -match '^\[\d+\]') {
            $taskMatch=[regex]::Match($taskText,'https?://\S+')
            if ($taskMatch.Success) {
                $url=$taskMatch.Value.TrimEnd('.')
                $linkRange=$taskParagraph.Range.Duplicate
                $linkRange.Start=$taskParagraph.Range.Start+$taskMatch.Index
                $linkRange.End=$linkRange.Start+$url.Length
                if ($linkRange.Hyperlinks.Count -eq 0) {[void]$taskDocument.Hyperlinks.Add($linkRange,$url)}
            }
        }
    }
    for ($pass=0;$pass -lt 3;$pass++) {
        [void]$taskDocument.Fields.Update()
        for ($j=1;$j -le $taskDocument.TablesOfFigures.Count;$j++) {$taskDocument.TablesOfFigures.Item($j).Update()}
        $taskDocument.Repaginate()
        for ($j=1;$j -le $taskDocument.TablesOfContents.Count;$j++) {$taskDocument.TablesOfContents.Item($j).Update()}
    }
    $taskDocument.Save()
    $taskDocument.ExportAsFixedFormat($PdfPath,17)
    $summary=[pscustomobject]@{Pages=$taskDocument.ComputeStatistics(2);TOCs=$taskDocument.TablesOfContents.Count;FigureLists=$taskDocument.TablesOfFigures.Count;Equations=$taskDocument.OMaths.Count;Output=$resolvedInput;PDF=$PdfPath}
    $summary | ConvertTo-Json -Compress
} finally {
    if ($null -ne $taskDocument) {$taskDocument.Close(0);[void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($taskDocument)}
    if ($ownsInstance -and $null -ne $taskWord) {$taskWord.Quit()}
    if ($null -ne $taskWord) {[void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($taskWord)}
    [GC]::Collect()
}
