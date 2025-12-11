Sub UpdateDateDropdown()
    Dim ws As Worksheet
    Dim rng As Range
    Dim i As Integer
    Dim startDate As Date
    Dim endDate As Date
    Dim dateList As String
    
    ' 設定工作表 (請依你的需求修改)
    Set ws = ActiveSheet
    
    ' 1. 設定日期範圍邏輯
    ' 起始日：上個月的 1 號 (例如現在12月，這會抓到 11/1)
    startDate = DateSerial(Year(Date), Month(Date) - 1, 1)
    
    ' 結束日：本月的最後一天 (例如現在12月，這會抓到 12/31)
    ' 邏輯：下個月的第0天 = 本月最後一天
    endDate = DateSerial(Year(Date), Month(Date) + 1, 0)
    
    ' 2. 建立下拉選單字串
    ' 這裡示範用倒序 (最新的日期在最上面)，如果想要順序，迴圈改成 startDate To endDate
    dateList = ""
    For i = 0 To (endDate - startDate)
        ' 從結束日往回推 (endDate - i)
        If dateList = "" Then
            dateList = Format(endDate - i, "yyyy/mm/dd")
        Else
            dateList = dateList & "," & Format(endDate - i, "yyyy/mm/dd")
        End If
    Next i
    
    ' 3. 將清單套用到儲存格驗證 (例如 A1 儲存格)
    Set rng = ws.Range("A1") ' <--- 請修改你要套用的儲存格位置
    
    With rng.Validation
        .Delete
        .Add Type:=xlValidateList, AlertStyle:=xlValidAlertStop, Operator:= _
        xlBetween, Formula1:=dateList
        .IgnoreBlank = True
        .InCellDropdown = True
        .ShowInput = True
        .ShowError = True
    End With
    
    MsgBox "下拉選單已更新：包含 " & Format(startDate, "mm/dd") & " 到 " & Format(endDate, "mm/dd")
    
End Sub
