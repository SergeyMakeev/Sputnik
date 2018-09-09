local g_Sputnik = require(script.Parent.SputnikModule)

local g_Toolbar = plugin:CreateToolbar("Sputnik")

----------------------------------------------------------------------------------------------------------
local g_CheckButton = g_Toolbar:CreateButton("Test", "Sputnik self-test system.", "rbxassetid://2049953838")
g_CheckButton.Click:connect(function()
	g_Sputnik.SelfTest()
end)

----------------------------------------------------------------------------------------------------------
local g_OpenFileButton = g_Toolbar:CreateButton("FileOpen", "Example open file dialog.", "rbxassetid://2049953840")

function onFileOpen(filePath)
	print("Open file: " .. filePath)
	
	local fileStat = g_Sputnik.Stat(filePath)
	print("is_exist: " .. tostring(fileStat.is_exist))
	print("is_dir: " .. tostring(fileStat.is_dir))
	print("is_file: " .. tostring(fileStat.is_file))
	print("size: " .. tostring(fileStat.size))
	
	local fileContent, fileLength = g_Sputnik.ReadFile(filePath)
	print("File size: " .. fileLength)
	print("File content:")
	print(fileContent)
end

function onOpenDialogClosed()
	print("Open dialog closed")
end

g_OpenFileButton.Click:connect(function()
	g_Sputnik:OpenFileDialog(plugin, onFileOpen, onOpenDialogClosed)
end)

----------------------------------------------------------------------------------------------------------
local g_SaveFileButton = g_Toolbar:CreateButton("FileSave", "Example save file dialog", "rbxassetid://2049953841")

function onFileSave(filePath)
	print("Save file: " .. filePath)
end

function onSaveDialogClosed()
	print("Save dialog closed")
end

g_SaveFileButton.Click:connect(function()
	g_Sputnik:SaveFileDialog(plugin, "test_file.txt", onFileSave, onSaveDialogClosed)
end)




----------------------------------------------------------------------------------------------------------
local g_SceneExportButton = g_Toolbar:CreateButton("Export", "Export scene from Roblox to Autodesk Maya", "rbxassetid://2053256596")

g_SceneExportButton.Click:connect(function()
	g_Sputnik.ExportScene("C:/Work/0/rbxl_test.mel")
end)


----------------------------------------------------------------------------------------------------------
local g_SceneImportButton = g_Toolbar:CreateButton("Import", "Import cframes from Autodesk Maya to Roblox", "rbxassetid://2053256595")

g_SceneImportButton.Click:connect(function()
	print("TODO")
end)



