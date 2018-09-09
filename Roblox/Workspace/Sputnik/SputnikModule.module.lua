--
-- Roblox Sputnik module
--

local SputnikModule = {}
SputnikModule.__index = SputnikModule
SputnikModule.ClassName = "SputnikModule"

local http = game:GetService("HttpService")
local serverUrl = "http://127.0.0.1:8002"

local g_CmdVer = "/ver"
local g_CmdGetCurDir = "/getcwd"
local g_CmdSetCurDir = "/chdir"
local g_CmdDirList = "/dirlist"
local g_CmdReadFile = "/read"
local g_CmdWriteFile = "/write"
local g_CmdStat = "/stat"
local g_CmdSceneExport = "/scene_export"


function BinaryEncodeByte(v)
	local h = math.floor(v / 16)
	local l = v - (h * 16)
	return string.char(h + 65,l + 97) 
end

function BinaryDecodeByte(h, l)
	h = h - 65
	l = l - 97
	return string.char(h * 16 + l)
end

function BinaryEncode(data)
	local res = ""
	local inputLen = string.len(data)
	for i = 1, inputLen, 1 do 
   		local bt = string.byte(data, i)
		res = res .. BinaryEncodeByte(bt)
	end
	return res
end

function BinaryDecode(data)
	local res = ""
	local inputLen = string.len(data)
	if ((inputLen % 2) > 0) then
		error("BinaryDecode: Invalid input")
	end
	for i = 1, inputLen, 2 do 
   		local h = string.byte(data, i)
		local l = string.byte(data, i + 1)
		res = res .. BinaryDecodeByte(h, l)
	end
	return res
end

----------------------------------------------------------------------------------------------------------
local function SputnikModuleSelfTest()
	print("Sputnik: Roblox plugin helper module")
	
	print("Sputnik: Binary Encode/Decode self-test")
	local guidRequest = http:GenerateGUID()
	local guidEncoded = BinaryEncode(guidRequest)
	local guidRequestTest = BinaryDecode(guidEncoded)
	if (guidRequest ~= guidRequestTest) then
		print("Expected : " .. guidRequest)
		print("Result : " .. guidRequestTest)
		error("Binary Encode/Decode is broken")
		return
	end
	
	print("Sputnik: Client/Server connection test")
	local success, json = pcall(http.GetAsync, http, (serverUrl .. g_CmdVer .. "?guid=" .. guidEncoded))
	if not success then
		error("Sputnik: Http request failed.\nGame Settings->Secutity->Allow HTTP requests should be enabled.\nSputnik Server should be runned.")
		return
	end
	
	local response = http:JSONDecode(json)
	if response.result ~= "ok" then
		error("Sputnik: Server return error")
		return
	end
	
	print("Sputnik: Client/Server binary Encode/Decode test")
	local guidResponse = BinaryDecode(response.guid)
	if (guidRequest ~= guidResponse) then
		print("Expected : " .. guidRequest)
		print("Result : " .. guidResponse)
		error("Binary Encode/Decode is broken")
		return
	end
	print("Sputnik: Self-test has passed")
	print("Sputnik: Server version : " .. response.ver)
	
	
end

----------------------------------------------------------------------------------------------------------
function SputnikModule.new()
	local self = setmetatable({}, SputnikModule)
	self.pluginFileDialogWindow = nil
	self.pluginFileDialogWindowFileList = nil
	self.pluginFileDialogFileName = nil
	self.pluginFileDialogIsOpened = false
	self.pluginFileDialogSelectedFile = nil
	self.pluginFileDialogOnFileAction = nil
	self.pluginFileDialogOnCancel = nil
	self.pluginFileDialogOnFocusReleased = nil
	self.pluginFileDialogOnFocusAcquired = nil
	self.pluginFileDialogFileActionButton = nil
	self.pluginFileDialogCancelButton = nil
	return self
end


----------------------------------------------------------------------------------------------------------
function SputnikModule.SelfTest()
	return SputnikModuleSelfTest()
end

----------------------------------------------------------------------------------------------------------
function SputnikModule.GetParentDirectory(dirName)
	local lastChar = string.sub(dirName, -1)
	if (lastChar ~= "/") then
		error("GetParentDirName error." .. dirName .. " should be a directory name")
		return nil
	end
	
	local _, count = string.gsub(dirName, "/", "")	
	if (count == 1) then
		return dirName
	end
	
	local dirNameWithoutTrailingSlash = dirName:sub(1, -2)
	local lastIndex = dirNameWithoutTrailingSlash:match("^.*()/")
	return dirNameWithoutTrailingSlash:sub(1, lastIndex)
end

----------------------------------------------------------------------------------------------------------
function SputnikModule.GetCurrentDirectory()
	local response = http:JSONDecode(http:GetAsync(serverUrl .. g_CmdGetCurDir))
	if response.result ~= "ok" then
		error("GetCurrentWorkingDir error")
		return nil
	end
	return response.dir
end

----------------------------------------------------------------------------------------------------------
function SputnikModule.SetCurrentDirectory(dirName)
	local lastChar = string.sub(dirName, -1)
	if (lastChar ~= "/") then
		error("SetCurrentWorkingDir error." .. dirName .. " should be a directory name")
		return nil
	end

	local dirNameWithoutTrailingSlash = dirName:sub(1, -2)
	local escapedDirName = dirNameWithoutTrailingSlash:gsub("/", "%%2F")
 	
	local json = http:PostAsync(serverUrl .. g_CmdSetCurDir .. "?dir=" .. escapedDirName, "")
	local response = http:JSONDecode(json)
	
	if response.result ~= "ok" then
		error("SetCurrentWorkingDir error")
		return nil
	end
end

----------------------------------------------------------------------------------------------------------
function SputnikModule.EnumerateDirectory(dirName)
	local lastChar = string.sub(dirName, -1)
	if (lastChar ~= "/") then
		error("EnumerateDirectory error." .. dirName .. " should be a directory name")
		return nil
	end

	local dirNameWithoutTrailingSlash = dirName:sub(1, -2)
	local escapedDirName = dirNameWithoutTrailingSlash:gsub("/", "%%2F")
	
	local json = http:GetAsync(serverUrl .. g_CmdDirList .. "?dir=" .. escapedDirName)
	local response = http:JSONDecode(json)
	if response.result ~= "ok" then
		error("EnumerateDirectory error")
		return nil
	end
	
	return response.dirs, response.files  
end  

----------------------------------------------------------------------------------------------------------
function SputnikModule.ReadFile(fileName)
	local lastChar = string.sub(fileName, -1)
	if (lastChar == "/") then
		error("ReadFile error." .. fileName .. " should be a file name")
		return nil
	end
	local escapedFileName = fileName:gsub("/", "%%2F")
	local json = http:GetAsync(serverUrl .. g_CmdReadFile .. "?file=" .. escapedFileName)
	local response = http:JSONDecode(json)
	if response.result ~= "ok" then
		error("ReadFile error")
		return nil
	end

	return BinaryDecode(response.content), response.size
end

----------------------------------------------------------------------------------------------------------
function SputnikModule.WriteFile(fileName, data)
	local lastChar = string.sub(fileName, -1)
	if (lastChar == "/") then
		error("WriteFile error." .. fileName .. " should be a file name")
		return nil
	end
	local escapedFileName = fileName:gsub("/", "%%2F")
	local dataEncoded = BinaryEncode(data)
	
	local json = http:PostAsync(serverUrl .. g_CmdWriteFile .. "?file=" .. escapedFileName, dataEncoded)
	local response = http:JSONDecode(json)
	
	if response.result ~= "ok" then
		error("WriteFile error")
		return nil
	end
end

----------------------------------------------------------------------------------------------------------
function SputnikModule.Stat(filePath)
	local escapedFilePath = filePath:gsub("/", "%%2F")
	local json = http:GetAsync(serverUrl .. g_CmdStat .. "?path=" .. escapedFilePath)
	local response = http:JSONDecode(json)

	if response.result ~= "ok" then
		error("Stat error")
		return nil
	end
	
	return response.payload
end

----------------------------------------------------------------------------------------------------------
function SputnikModule:_RefreshFileDialog()
	
	if (self.pluginFileDialogWindowFileList == nil) then
		error("pluginFileDialogWindowFileList can't be nil")
		return
	end
	
	self.pluginFileDialogWindowFileList:ClearAllChildren()
	
	local listLayout = Instance.new("UIListLayout")
	listLayout.Parent = self.pluginFileDialogWindowFileList
	
	local currentDir = SputnikModule.GetCurrentDirectory()
	
	local parentDir = SputnikModule.GetParentDirectory(currentDir)
	if (parentDir ~= currentDir) then
		local item = Instance.new("TextButton")
		item.BorderSizePixel = 0
		item.Font = Enum.Font.Code
		item.TextXAlignment = Enum.TextXAlignment.Left
		item.Text = " .." 
		item.Parent = self.pluginFileDialogWindowFileList
		item.Size = UDim2.new(1.0, 0, 0, 14)
		item.MouseButton1Down:connect(function()
			SputnikModule.SetCurrentDirectory(parentDir)
			self:_RefreshFileDialog()
		end)			
	end	
	
	local dirs, files = SputnikModule.EnumerateDirectory(currentDir)
	
	for _, v in ipairs(dirs) do
		local item = Instance.new("TextButton")
		item.BorderSizePixel = 0
		item.Font = Enum.Font.Code
		item.TextXAlignment = Enum.TextXAlignment.Left
		item.Text = " " .. v.short_name 
		item.Parent = self.pluginFileDialogWindowFileList
		item.Size = UDim2.new(1.0, 0, 0, 14)
		item.MouseButton1Down:connect(function()
			SputnikModule.SetCurrentDirectory(v.long_name)
			self:_RefreshFileDialog()
		end)			
	end
	
	for _, v in ipairs(files) do
		local item = Instance.new("TextButton")
		item.BorderSizePixel = 0
		item.Font = Enum.Font.Code
		item.TextXAlignment = Enum.TextXAlignment.Left
		item.Text = " " .. v.short_name 
		item.Size = UDim2.new(1.0, 0, 0, 14)
		item.Parent = self.pluginFileDialogWindowFileList
		item.MouseButton1Down:connect(function()
			self.pluginFileDialogFileName.Text = v.short_name
			self.pluginFileDialogSelectedFile = v
		end)			
	end
end

----------------------------------------------------------------------------------------------------------
function SputnikModule:_CreateFileDialogIfNeed(pluginApi)
	if (self.pluginFileDialogIsOpened == true) then
		error("File dialog window is already opened")
		return
	end

	if (self.pluginFileDialogWindow ~= nil) then
		return
	end
	
	local info = DockWidgetPluginGuiInfo.new( Enum.InitialDockState.Float, true, true, 200, 100 )
	local pluginFileDialogWindow = pluginApi:CreateDockWidgetPluginGui("SputnikFileDialog", info)
	
	pluginFileDialogWindow.WindowFocusReleased:connect(function()
		if (self.pluginFileDialogOnFocusReleased ~= nil) then
			self.pluginFileDialogOnFocusReleased()
		end
	end) 	

	pluginFileDialogWindow.WindowFocused:connect(function()
		if (self.pluginFileDialogOnFocusAcquired ~= nil) then
			self.pluginFileDialogOnFocusAcquired()
		end
	end) 	
	
	pluginFileDialogWindow.Changed:connect(function(property)
		if(pluginFileDialogWindow.Enabled == false and self.pluginFileDialogIsOpened == true) then
			if (self.pluginFileDialogOnCancel ~= nil) then
				self.pluginFileDialogOnCancel()
				self.pluginFileDialogIsOpened = false
			end
		end
	end) 	
	
	local pluginFileDialogWindowFileList = Instance.new("ScrollingFrame")
	pluginFileDialogWindowFileList.AnchorPoint = Vector2.new(0.0, 0.0)
	pluginFileDialogWindowFileList.Position = UDim2.new(0.02, 0, 0.02, 0)
	pluginFileDialogWindowFileList.Size = UDim2.new(0.95, 0, 0.9, 0)
	pluginFileDialogWindowFileList.SizeConstraint = Enum.SizeConstraint.RelativeXY
	pluginFileDialogWindowFileList.Parent = pluginFileDialogWindow
	
	local pluginFileDialogFileName = Instance.new("TextBox")
	pluginFileDialogFileName.Font = Enum.Font.Code
	pluginFileDialogFileName.AnchorPoint = Vector2.new(0.0, 0.0)
	pluginFileDialogFileName.Position = UDim2.new(0.02, 0, 0.94, 0)
	pluginFileDialogFileName.Size = UDim2.new(0.68, 0, 0, 20)
	pluginFileDialogFileName.SizeConstraint = Enum.SizeConstraint.RelativeXY
	pluginFileDialogFileName.Text = ""
	pluginFileDialogFileName.TextXAlignment = Enum.TextXAlignment.Left
	pluginFileDialogFileName.Parent = pluginFileDialogWindow
	
	local pluginFileDialogFileActionButton = Instance.new("TextButton")
	pluginFileDialogFileActionButton.Font = Enum.Font.Code
	pluginFileDialogFileActionButton.AnchorPoint = Vector2.new(0.0, 0.0)
	pluginFileDialogFileActionButton.Position = UDim2.new(0.705, 0, 0.94, 0)
	pluginFileDialogFileActionButton.Size = UDim2.new(0.13, 0, 0, 20)
	pluginFileDialogFileActionButton.SizeConstraint = Enum.SizeConstraint.RelativeXY
	pluginFileDialogFileActionButton.Text = "Open"
	pluginFileDialogFileActionButton.Parent = pluginFileDialogWindow
	pluginFileDialogFileActionButton.MouseButton1Down:connect(function()
		local currentDir = SputnikModule.GetCurrentDirectory()
		local currentFile = self.pluginFileDialogFileName.Text
		local longFileName = currentDir .. currentFile  
		self.pluginFileDialogOnFileAction(longFileName)
		self.pluginFileDialogIsOpened = false
		self.pluginFileDialogWindow.Enabled = false
	end)			
	
	
	local pluginFileDialogCancelButton = Instance.new("TextButton")
	pluginFileDialogCancelButton.Font = Enum.Font.Code
	pluginFileDialogCancelButton.AnchorPoint = Vector2.new(0.0, 0.0)
	pluginFileDialogCancelButton.Position = UDim2.new(0.84, 0, 0.94, 0)
	pluginFileDialogCancelButton.Size = UDim2.new(0.13, 0, 0, 20)
	pluginFileDialogCancelButton.SizeConstraint = Enum.SizeConstraint.RelativeXY
	pluginFileDialogCancelButton.Text = "Cancel"
	pluginFileDialogCancelButton.Parent = pluginFileDialogWindow
	pluginFileDialogCancelButton.MouseButton1Down:connect(function()
		self.pluginFileDialogWindow.Enabled = false
	end)			
	
	self.pluginFileDialogWindow = pluginFileDialogWindow
	self.pluginFileDialogWindowFileList = pluginFileDialogWindowFileList
	self.pluginFileDialogFileName = pluginFileDialogFileName 
	self.pluginFileDialogFileActionButton = pluginFileDialogFileActionButton
	self.pluginFileDialogCancelButton = pluginFileDialogCancelButton


end

----------------------------------------------------------------------------------------------------------
function SputnikModule:OpenFileDialog(pluginApi, onFileOpen, onCancel, onFocusReleased, onFocusAcquired)
	
	if (onFileOpen == nil) then
		error("You should provide onFileOpen handler")
		return
	end
	
	self:_CreateFileDialogIfNeed(pluginApi)
	
	if (self.pluginFileDialogWindow == nil) then
		error("Sputnik: Error. Can't create plugin window for a file dialog")
		return
	end
	
	self.pluginFileDialogFileName.Text = ""
	self.pluginFileDialogFileActionButton.Text = "Open"
	
	self.pluginFileDialogOnFileAction = onFileOpen
	self.pluginFileDialogOnCancel = onCancel
	self.pluginFileDialogOnFocusReleased = onFocusReleased
	self.pluginFileDialogOnFocusAcquired = onFocusAcquired

	self.pluginFileDialogIsOpened = true	
	self:_RefreshFileDialog()
	self.pluginFileDialogWindow.Enabled = true
end

----------------------------------------------------------------------------------------------------------
function SputnikModule:SaveFileDialog(pluginApi, defaultFileName, onFileSave, onCancel, onFocusReleased, onFocusAcquired)
	
	if (onFileSave == nil) then
		error("You should provide onFileSave handler")
		return
	end
	
	self:_CreateFileDialogIfNeed(pluginApi)
	
	if (self.pluginFileDialogWindow == nil) then
		error("Sputnik: Error. Can't create plugin window for a file dialog")
		return
	end
	
	self.pluginFileDialogFileName.Text = defaultFileName
	self.pluginFileDialogFileActionButton.Text = "Save"
	
	self.pluginFileDialogOnFileAction = onFileSave
	self.pluginFileDialogOnCancel = onCancel
	self.pluginFileDialogOnFocusReleased = onFocusReleased
	self.pluginFileDialogOnFocusAcquired = onFocusAcquired

	self.pluginFileDialogIsOpened = true	
	self:_RefreshFileDialog()
	self.pluginFileDialogWindow.Enabled = true
end

----------------------------------------------------------------------------------------------------------
function SputnikModule.ExportScene(fileName)
	local lastChar = string.sub(fileName, -1)
	if (lastChar == "/") then
		error("ExportScene error." .. fileName .. " should be a file name")
		return nil
	end
	local escapedFileName = fileName:gsub("/", "%%2F")
	
	
	--
	local descendants = workspace:GetDescendants()
	local sceneObjects = {}

	for index, descendant in pairs(descendants) do
		
		local desc = {}
		desc.name = descendant.Name		
		desc.full_name = descendant:GetFullName()
		desc.mesh_id = ""
		desc.shape = ""
		desc.pos_x = 0
		desc.pos_y = 0
		desc.pos_z = 0
		desc.rot_x = 0 
		desc.rot_y = 0
		desc.rot_z = 0
		desc.scl_x = 1
		desc.scl_y = 1
		desc.scl_z = 1
		
		if descendant:IsA("Part") then
			desc.pos_x = descendant.CFrame.x
			desc.pos_y = descendant.CFrame.y
			desc.pos_z = descendant.CFrame.z
			desc.rot_x, desc.rot_y, desc.rot_z = descendant.CFrame:toEulerAnglesXYZ()
			desc.scl_x = descendant.Size.x
			desc.scl_y = descendant.Size.y
			desc.scl_z = descendant.Size.z
			desc.shape = tostring(descendant.Shape)
			table.insert(sceneObjects, desc)
		elseif descendant:IsA("MeshPart") then
			desc.mesh_id = descendant.MeshId
			desc.pos_x = descendant.CFrame.x
			desc.pos_y = descendant.CFrame.y
			desc.pos_z = descendant.CFrame.z
			desc.rot_x, desc.rot_y, desc.rot_z = descendant.CFrame:toEulerAnglesXYZ()
			desc.scl_x = descendant.Size.x
			desc.scl_y = descendant.Size.y
			desc.scl_z = descendant.Size.z
			desc.shape = "MeshPart"
			table.insert(sceneObjects, desc)
		elseif descendant:IsA("SpecialMesh") then
			desc.mesh_id = descendant.MeshId
			desc.pos_x = descendant.Parent.CFrame.x
			desc.pos_y = descendant.Parent.CFrame.y
			desc.pos_z = descendant.Parent.CFrame.z
			desc.rot_x, desc.rot_y, desc.rot_z = descendant.Parent.CFrame:toEulerAnglesXYZ()
			desc.scl_x = descendant.Scale.x
			desc.scl_y = descendant.Scale.y
			desc.scl_z = descendant.Scale.z
			desc.shape = "SpecialMesh"
			table.insert(sceneObjects, desc)
		else
			-- unsupported object type
		end		
	end	

	local sceneJson = http:JSONEncode(sceneObjects)
	
	local json = http:PostAsync(serverUrl .. g_CmdSceneExport .. "?file=" .. escapedFileName, sceneJson)
	local response = http:JSONDecode(json)
	
	if response.result ~= "ok" then
		error("ExportScene error")
		return nil
	end
	
	print("ExportScene - ok")
	
end




return SputnikModule.new() 
